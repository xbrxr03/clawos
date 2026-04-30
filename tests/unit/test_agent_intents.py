# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for runtimes/agent/intents.py — deterministic intent classifier."""
from runtimes.agent.intents import Intent, classify


class TestGreetings:
    def test_hi(self):
        assert classify("hi").intent == Intent.GREETING

    def test_hello_with_punctuation(self):
        assert classify("Hello!").intent == Intent.GREETING

    def test_good_morning_triggers_briefing(self):
        # "good morning" to JARVIS triggers the morning briefing — this is
        # the canonical JARVIS-style behaviour, not a plain greeting.
        assert classify("good morning").intent == Intent.MORNING_BRIEFING

    def test_morning_briefing_explicit(self):
        assert classify("good morning briefing").intent == Intent.MORNING_BRIEFING
        assert classify("brief me").intent == Intent.MORNING_BRIEFING


class TestAcks:
    def test_ok(self):
        assert classify("ok").intent == Intent.ACK

    def test_thanks(self):
        assert classify("thanks").intent == Intent.ACK

    def test_got_it(self):
        assert classify("got it").intent == Intent.ACK


class TestVolume:
    def test_set_explicit(self):
        m = classify("set volume to 70")
        assert m.intent == Intent.VOLUME_SET
        assert m.args["level"] == 70

    def test_volume_up(self):
        m = classify("volume up")
        assert m.intent == Intent.VOLUME_SET
        assert m.args["direction"] == "up"

    def test_volume_clamps(self):
        m = classify("set volume to 250")
        assert m.args["level"] == 100

    def test_mute(self):
        m = classify("mute")
        assert m.intent == Intent.VOLUME_SET
        assert m.args["direction"] == "mute"


class TestApps:
    def test_open_spotify(self):
        m = classify("open spotify")
        assert m.intent == Intent.APP_OPEN
        assert m.args["app"] == "spotify"

    def test_launch_firefox(self):
        m = classify("launch firefox")
        assert m.intent == Intent.APP_OPEN
        assert m.args["app"] == "firefox"

    def test_open_the_door_blocked(self):
        # "open the door" shouldn't try to launch an app called "the door"
        m = classify("open the door")
        # Falls through to LLM (not app open)
        assert m.intent != Intent.APP_OPEN


class TestReminders:
    def test_remind_me(self):
        m = classify("remind me to buy milk at 7pm")
        assert m.intent == Intent.REMINDER_ADD
        assert "milk" in m.args["task"]
        assert "7pm" in m.args["when"]

    def test_list_reminders(self):
        assert classify("list my reminders").intent == Intent.REMINDER_LIST
        assert classify("what are my reminders").intent == Intent.REMINDER_LIST


class TestTime:
    def test_what_time(self):
        assert classify("what time is it").intent == Intent.TIME_QUERY
        assert classify("what's the time").intent == Intent.TIME_QUERY


class TestMemoryRecall:
    def test_what_did_i_tell_you(self):
        m = classify("what did I tell you about my dog")
        assert m.intent == Intent.MEMORY_RECALL
        assert "dog" in m.args["topic"]

    def test_remind_me_what(self):
        m = classify("remind me what cron is")
        assert m.intent == Intent.MEMORY_RECALL


class TestFallthrough:
    def test_complex_task_falls_through(self):
        m = classify("write me an essay about cats and put it in a notepad file")
        assert m.intent == Intent.LLM_NEEDED

    def test_question_falls_through(self):
        m = classify("why is the sky blue")
        assert m.intent == Intent.LLM_NEEDED

    def test_empty_input(self):
        assert classify("").intent == Intent.LLM_NEEDED
        assert classify("   ").intent == Intent.LLM_NEEDED
