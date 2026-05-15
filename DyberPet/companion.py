import json
import os
import random
from datetime import datetime, timedelta

import DyberPet.settings as settings


class OfflineCompanion:
    """Offline, rule-based companion bubble generator."""

    RETURN_THRESHOLD = timedelta(minutes=30)
    IDLE_THRESHOLD = timedelta(minutes=45)
    QUIET_HOURS = ((23, 24), (0, 6))
    DAILY_LIMITS = {
        "low": 6,
        "medium": 10,
        "high": 14,
    }
    FREQUENCY_SCALE = {
        "low": 1.0,
        "medium": 0.75,
        "high": 0.5,
    }
    BASE_COOLDOWNS = {
        "companion_patpat": 20,
        "companion_return": 20,
        "companion_focus_start": 15,
        "companion_focus_end": 15,
        "companion_working": 30 * 60,
        "companion_late_night": 60 * 60,
        "companion_idle_presence": 60 * 60,
    }
    ICON_MAP = {
        "companion_greeting": "bb_companion_greeting",
        "companion_patpat": "bb_companion_patpat",
        "companion_focus_start": "bb_companion_focus_start",
        "companion_focus_end": "bb_companion_focus_end",
        "companion_late_night": "bb_companion_late_night",
        "companion_working": "bb_companion_working",
        "companion_idle_presence": "bb_companion_idle_presence",
        "companion_return": "bb_companion_return",
    }
    APP_CATEGORY_PATTERNS = {
        "ide": ["code", "pycharm", "idea", "intellij", "visual studio", "devenv", "cursor", "windsurf"],
        "design": ["photoshop", "figma", "illustrator", "afterfx", "after effects", "xd"],
        "office": ["word", "excel", "powerpoint", "wps", "outlook"],
        "browser": ["chrome", "msedge", "edge", "firefox", "safari", "opera", "browser"],
        "explorer": ["explorer", "finder", "files"],
    }

    def __init__(self):
        self.config = self._load_config()
        self.last_user_interaction_at = None
        self.last_companion_bubble_at = None
        self.last_context_type = None
        self.last_context_times = {}
        self.daily_trigger_date = None
        self.daily_trigger_count = 0

    def _load_config(self):
        conf_path = os.path.join(settings.BASEDIR, "res", "icons", "companion_conf.json")
        with open(conf_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _pattern_map(self):
        pattern_map = dict(self.APP_CATEGORY_PATTERNS)
        config_patterns = self.config.get("_app_category_patterns", {})
        for category, patterns in config_patterns.items():
            if isinstance(patterns, list) and patterns:
                pattern_map[category] = [str(pattern).lower() for pattern in patterns if str(pattern).strip()]
        return pattern_map

    def _app_blacklist(self):
        raw = self.config.get("_app_blacklist", [])
        if not isinstance(raw, list):
            return []
        return [str(item).lower() for item in raw if str(item).strip()]

    def _language_key(self):
        return "zh_CN" if settings.language_code.startswith("zh") else "en_US"

    def _now(self):
        return datetime.now()

    def _quiet_hours_active(self, now):
        hour = now.hour
        for start, end in self.QUIET_HOURS:
            if start <= hour < end:
                return True
        return False

    def _frequency(self):
        value = getattr(settings, "companion_frequency", "low")
        return value if value in self.FREQUENCY_SCALE else "low"

    def _daily_limit_reached(self, now):
        if self.daily_trigger_date != now.date():
            self.daily_trigger_date = now.date()
            self.daily_trigger_count = 0
        return self.daily_trigger_count >= self.DAILY_LIMITS[self._frequency()]

    def _mark_triggered(self, context_type, now, proactive=False):
        self.last_companion_bubble_at = now
        self.last_context_type = context_type
        self.last_context_times[context_type] = now
        if proactive:
            if self.daily_trigger_date != now.date():
                self.daily_trigger_date = now.date()
                self.daily_trigger_count = 0
            self.daily_trigger_count += 1

    def _cooldown_seconds(self, context_type):
        scale = self.FREQUENCY_SCALE[self._frequency()]
        return int(self.BASE_COOLDOWNS.get(context_type, 30) * scale)

    def _general_proactive_gap_ok(self, now):
        if self.last_companion_bubble_at is None:
            return True
        gap = (now - self.last_companion_bubble_at).total_seconds()
        return gap >= int(20 * 60 * self.FREQUENCY_SCALE[self._frequency()])

    def _context_cooldown_ok(self, context_type, now):
        last_time = self.last_context_times.get(context_type)
        if last_time is None:
            return True
        return (now - last_time).total_seconds() >= self._cooldown_seconds(context_type)

    def _pick_message(self, context_type, **filters):
        context_conf = self.config.get(context_type, {})
        entries = context_conf.get(self._language_key(), [])
        candidates = []

        for entry in entries:
            if isinstance(entry, str):
                entry = {"message": entry}

            app_categories = entry.get("app_category")
            if app_categories and filters.get("app_category") not in app_categories:
                continue

            focus_only = entry.get("focus_only")
            if focus_only is True and not filters.get("focus_mode_active"):
                continue
            if focus_only is False and filters.get("focus_mode_active"):
                continue

            night_only = entry.get("night_only")
            if night_only is True and not filters.get("quiet_hours_active"):
                continue
            if night_only is False and filters.get("quiet_hours_active"):
                continue

            time_range = entry.get("time_range")
            if time_range:
                hour = filters.get("hour")
                if hour is None or not self._hour_in_ranges(hour, time_range):
                    continue

            min_focus_elapsed = entry.get("min_focus_elapsed")
            if min_focus_elapsed is not None:
                focus_elapsed_minutes = filters.get("focus_elapsed_minutes")
                if focus_elapsed_minutes is None or focus_elapsed_minutes < min_focus_elapsed:
                    continue

            max_focus_elapsed = entry.get("max_focus_elapsed")
            if max_focus_elapsed is not None:
                focus_elapsed_minutes = filters.get("focus_elapsed_minutes")
                if focus_elapsed_minutes is None or focus_elapsed_minutes > max_focus_elapsed:
                    continue

            candidates.append(entry["message"])

        if not candidates:
            return ""
        return random.choice(candidates)

    def _hour_in_ranges(self, hour, ranges):
        for start, end in ranges:
            if start <= end and start <= hour < end:
                return True
            if start > end and (hour >= start or hour < end):
                return True
        return False

    def _replace_tokens(self, message, **kwargs):
        usertag = settings.usertag_dict.get(settings.petname, "").strip()
        if usertag:
            message = message.replace("USERTAG", usertag)
        else:
            message = message.replace("USERTAG", "")

        app_name = kwargs.get("app_name", "").strip()
        if app_name:
            message = message.replace("APPNAME", app_name)
        else:
            message = message.replace("APPNAME", "")

        return " ".join(message.split())

    def _build_bubble(self, context_type, proactive=False, **filters):
        now = filters.get("now") or self._now()
        message = self._pick_message(
            context_type,
            app_category=filters.get("app_category"),
            focus_mode_active=filters.get("focus_mode_active", False),
            focus_elapsed_minutes=filters.get("focus_elapsed_minutes"),
            quiet_hours_active=filters.get("quiet_hours_active", self._quiet_hours_active(now)),
            hour=now.hour,
        )
        if not message:
            return None

        self._mark_triggered(context_type, now, proactive=proactive)
        return {
            "bubble_type": context_type,
            "icon": self.ICON_MAP.get(context_type),
            "message": self._replace_tokens(message, **filters),
            "start_audio": None,
            "end_audio": None,
        }

    def classify_surface(self, surface):
        name_candidates = []
        if surface is not None:
            name_candidates.extend([getattr(surface, "app_name", ""), getattr(surface, "owner", "")])

        combined = " ".join(v.lower() for v in name_candidates if v)
        if any(pattern in combined for pattern in self._app_blacklist()):
            return "general"
        for category, patterns in self._pattern_map().items():
            if any(pattern in combined for pattern in patterns):
                return category
        return "general"

    def display_app_name(self, surface):
        if surface is None:
            return ""
        return getattr(surface, "app_name", "") or getattr(surface, "owner", "")

    def get_greeting_bubble(self):
        if not getattr(settings, "companion_enabled", True):
            return None
        return self._build_bubble("companion_greeting", now=self._now())

    def handle_patpat(self, focus_elapsed_minutes=None):
        now = self._now()
        previous_interaction = self.last_user_interaction_at
        self.last_user_interaction_at = now

        if not getattr(settings, "companion_enabled", True):
            return None

        if previous_interaction and now - previous_interaction >= self.RETURN_THRESHOLD:
            if self._context_cooldown_ok("companion_return", now):
                return self._build_bubble(
                    "companion_return",
                    now=now,
                    focus_mode_active=settings.focus_timer_on,
                    focus_elapsed_minutes=focus_elapsed_minutes,
                )

        if self._context_cooldown_ok("companion_patpat", now):
            return self._build_bubble(
                "companion_patpat",
                now=now,
                focus_mode_active=settings.focus_timer_on,
                focus_elapsed_minutes=focus_elapsed_minutes,
            )
        return None

    def get_focus_bubble(self, context_type):
        if not getattr(settings, "companion_enabled", True):
            return None
        now = self._now()
        if not self._context_cooldown_ok(context_type, now):
            return None
        return self._build_bubble(context_type, now=now)

    def get_proactive_bubble(self, surface=None):
        now = self._now()
        if not getattr(settings, "companion_enabled", True):
            return None
        if not getattr(settings, "companion_proactive", True):
            return None
        if settings.focus_timer_on:
            return None
        if self._daily_limit_reached(now):
            return None
        if not self._general_proactive_gap_ok(now):
            return None

        quiet_hours_active = self._quiet_hours_active(now)
        if quiet_hours_active and getattr(settings, "companion_night", True):
            if self._context_cooldown_ok("companion_late_night", now):
                return self._build_bubble(
                    "companion_late_night",
                    proactive=True,
                    now=now,
                    quiet_hours_active=True,
                )

        if getattr(settings, "companion_contextual", True):
            app_category = self.classify_surface(surface)
            if app_category in {"ide", "design", "office"} and self._context_cooldown_ok("companion_working", now):
                return self._build_bubble(
                    "companion_working",
                    proactive=True,
                    now=now,
                    app_category=app_category,
                    app_name=self.display_app_name(surface),
                    quiet_hours_active=quiet_hours_active,
                )

        if self.last_user_interaction_at and now - self.last_user_interaction_at >= self.IDLE_THRESHOLD:
            if self._context_cooldown_ok("companion_idle_presence", now):
                return self._build_bubble(
                    "companion_idle_presence",
                    proactive=True,
                    now=now,
                    quiet_hours_active=quiet_hours_active,
                )

        return None
