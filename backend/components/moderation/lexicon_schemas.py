"""Strict server-side schema for versioned moderation dictionary administration."""
from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, model_validator

from components.moderation.lexicon_matcher import MAX_RULES, MAX_RULE_CHARS, MAX_TEXT_CHARS

LexiconAction = Literal["warn", "mask", "reject", "hold"]
LexiconMatchType = Literal["token", "phrase", "stem"]
LexiconCategory = Literal["profanity", "harassment", "hate", "fraud", "spam", "other"]
LexiconSurface = Literal["all", "space_chat", "messenger_plaintext", "profile", "activity", "post", "comment", "story", "reel", "media_caption"]


class LexiconRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: UUID = Field(default_factory=uuid4)
    term: str = Field(min_length=2, max_length=MAX_RULE_CHARS)
    language: Literal["ru", "en"] = "ru"
    category: LexiconCategory = "profanity"
    match_mode: LexiconMatchType = "token"
    action: LexiconAction = "mask"
    severity: Literal["low", "medium", "high"] = "medium"
    surfaces: list[LexiconSurface] = Field(default_factory=lambda: ["all"], min_length=1, max_length=10)
    variants: list[str] = Field(default_factory=list, max_length=20)
    exceptions: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_rule(self):
        self.term = self.term.strip()
        if len(set(self.surfaces)) != len(self.surfaces) or ("all" in self.surfaces and len(self.surfaces) > 1):
            raise ValueError("lexicon_duplicate_or_ambiguous_surface")
        self.variants = [term.strip() for term in self.variants]
        self.exceptions = [term.strip() for term in self.exceptions]
        for item in [self.term, *self.variants, *self.exceptions]:
            if len(item) < 2 or len(item) > MAX_RULE_CHARS:
                raise ValueError("lexicon_invalid_term_length")
            if any(unicodedata.category(ch) in ("Cc", "Cs", "Cf") for ch in item):
                raise ValueError("lexicon_control_character")
            if not any(ch.isalpha() for ch in item):
                raise ValueError("lexicon_term_needs_letters")
        if self.match_mode == "stem" and (len(self.term) < 4 or any(not ch.isalpha() for ch in self.term)):
            raise ValueError("lexicon_stem_requires_four_letters")
        if self.match_mode != "phrase" and any(ch.isspace() for ch in [self.term, *self.variants]):
            raise ValueError("lexicon_word_mode_no_whitespace")
        if len(set(x.casefold() for x in [self.term, *self.variants])) != len([self.term, *self.variants]):
            raise ValueError("lexicon_duplicate_variant")
        return self


class LexiconRevisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: list[LexiconRuleInput] = Field(default_factory=list, max_length=MAX_RULES)
    reason: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_revision(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 5:
            raise ValueError("lexicon_reason_required")
        if len({str(r.uid) for r in self.rules}) != len(self.rules):
            raise ValueError("lexicon_duplicate_rule_uid")
        return self


class LexiconActivate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    mode: Literal["off", "shadow"] = "shadow"
    reason: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def clean(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 5:
            raise ValueError("lexicon_reason_required")
        if self.revision == 0 and self.mode != "off":
            raise ValueError("lexicon_empty_cannot_activate")
        return self


class LexiconSimulate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=MAX_TEXT_CHARS)
    revision: int | None = Field(default=None, ge=0)
    rules: list[LexiconRuleInput] | None = Field(default=None, max_length=MAX_RULES)
