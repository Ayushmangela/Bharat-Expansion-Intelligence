"""Six-step geography resolution engine. See docs/04-ETL-PIPELINE.md.

resolve(observed_state, observed_district=None, observed_pin=None) -> Resolution

Nothing reaches gold unresolved. Districts are always disambiguated by
(state, district), never district alone.
"""

import re
import unicodedata
from dataclasses import dataclass

import psycopg


def normalise(text: str | None) -> str:
    """Step 1: strip, collapse whitespace, casefold, remove zero-width chars,
    expand '&' -> 'and', drop punctuation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("﻿", "")
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


@dataclass
class Resolution:
    lgd_state_code: int | None
    lgd_district_code: int | None
    method: str  # exact | alias | pin | fuzzy | unresolved
    confidence: float
    is_fuzzy: bool = False


class GeographyResolver:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self._state_index: dict[str, int] = {}
        self._district_index: dict[tuple[int, str], int] = {}
        self._alias_index: dict[tuple[str, str], tuple[int, int | None]] = {}
        self._subdistrict_index: dict[tuple[int, str], int] = {}
        self._load_indexes()

    def _load_indexes(self) -> None:
        for state_code, state_name in self.conn.execute(
            "SELECT lgd_state_code, state_name FROM gold.dim_geography WHERE grain = 'state' AND is_current"
        ).fetchall():
            self._state_index[normalise(state_name)] = state_code

        for state_code, district_code, district_name in self.conn.execute(
            "SELECT lgd_state_code, lgd_district_code, district_name FROM gold.dim_geography "
            "WHERE grain = 'district' AND is_current"
        ).fetchall():
            self._district_index[(state_code, normalise(district_name))] = district_code

        for state_code, district_code, subdistrict_name in self.conn.execute(
            "SELECT lgd_state_code, lgd_district_code, subdistrict_name FROM silver.lgd_subdistrict_lookup"
        ).fetchall():
            self._subdistrict_index[(state_code, normalise(subdistrict_name))] = district_code

        for observed_state, observed_district, lgd_state_code, lgd_district_code in self.conn.execute(
            "SELECT observed_state, observed_district, lgd_state_code, lgd_district_code FROM silver.geography_alias"
        ).fetchall():
            key = (normalise(observed_state), normalise(observed_district) if observed_district else "")
            self._alias_index[key] = (lgd_state_code, lgd_district_code)

    def resolve_state(self, observed_state: str) -> tuple[int | None, str]:
        norm = normalise(observed_state)
        if norm in self._state_index:
            return self._state_index[norm], "exact"
        alias_key = (norm, "")
        if alias_key in self._alias_index:
            return self._alias_index[alias_key][0], "alias"
        return None, "unresolved"

    def resolve(
        self,
        observed_state: str | None,
        observed_district: str | None = None,
        observed_pin: str | None = None,
        address_text: str | None = None,
    ) -> Resolution:
        state_code, state_method = (self.resolve_state(observed_state) if observed_state else (None, "unresolved"))

        # Step 4: PIN path, independent of whether state resolved by name —
        # useful when state text is missing/garbled but a PIN is present.
        # Two PIN sources, tried in order:
        #  (a) Dept of Posts pincode directory — direct district TEXT field,
        #      resolved through the normal state/district text path (not a
        #      raw LGD code), so it benefits from alias/fuzzy matching too.
        #  (b) LGD local-body PIN join — only covers PINs whose local body is
        #      itself a District Panchayat entity (~60% of PINs); kept as a
        #      fallback for the codes the postal directory doesn't cover.
        if observed_pin and re.fullmatch(r"\d{6}", observed_pin):
            row = self.conn.execute(
                "SELECT observed_state, observed_district FROM silver.pincode_district_lookup WHERE pincode = %s",
                (observed_pin,),
            ).fetchone()
            if row:
                pin_state_text, pin_district_text = row
                pin_state_code, _ = self.resolve_state(pin_state_text)
                if pin_state_code and (state_code is None or state_code == pin_state_code):
                    key = (pin_state_code, normalise(pin_district_text))
                    if key in self._district_index:
                        return Resolution(pin_state_code, self._district_index[key], "pin_postal", 0.92)

            row = self.conn.execute(
                "SELECT lgd_state_code, lgd_district_code FROM silver.lgd_pincode_lookup "
                "WHERE pincode = %s AND lgd_district_code IS NOT NULL LIMIT 1",
                (observed_pin,),
            ).fetchone()
            if row:
                pin_state, pin_district = row
                if state_code is None or state_code == pin_state:
                    return Resolution(pin_state, pin_district, "pin_lgd", 0.9)

        if state_code is None:
            return Resolution(None, None, "unresolved", 0.0)

        if not observed_district and not address_text:
            return Resolution(state_code, None, state_method, 1.0 if state_method == "exact" else 0.85)

        # Step 2: exact district match
        candidates = [observed_district] if observed_district else []
        if address_text:
            candidates.append(address_text)

        for cand in candidates:
            norm_district = normalise(cand)
            if not norm_district:
                continue
            key = (state_code, norm_district)
            if key in self._district_index:
                return Resolution(state_code, self._district_index[key], "exact", 1.0)

        # Step 3: alias lookup
        if observed_district:
            alias_key = (normalise(observed_state or ""), normalise(observed_district))
            if alias_key in self._alias_index:
                a_state, a_district = self._alias_index[alias_key]
                if a_district is not None:
                    return Resolution(a_state, a_district, "alias", 0.95)

        # Step 4b: address text contains a known district name verbatim
        # (common in MCA free-text addresses — cheaper and more reliable
        # than trigram similarity when the literal name is present).
        if address_text:
            norm_addr = normalise(address_text)
            for (s_code, d_norm), d_code in self._district_index.items():
                if s_code == state_code and d_norm and f" {d_norm} " in f" {norm_addr} ":
                    return Resolution(state_code, d_code, "address_contains", 0.9)

        # Step 4c: address text contains a known SUB-district (taluka/tehsil)
        # name. Real MCA addresses reference talukas/cities far more often
        # than the district itself (e.g. "Salcete", "Vasco-da-Gama" rather
        # than "South Goa"). Longest match wins to avoid a short substring
        # (e.g. "Goa") shadowing a more specific one.
        if address_text:
            norm_addr = normalise(address_text)
            best: tuple[int, int] | None = None  # (district_code, match_len)
            for (s_code, sd_norm), d_code in self._subdistrict_index.items():
                if (
                    s_code == state_code
                    and sd_norm
                    and f" {sd_norm} " in f" {norm_addr} "
                    and (best is None or len(sd_norm) > best[1])
                ):
                    best = (d_code, len(sd_norm))
            if best:
                return Resolution(state_code, best[0], "subdistrict_contains", 0.88)

        # Step 5: fuzzy match via pg_trgm, scoped to state, similarity >= 0.85
        probe = observed_district or address_text
        if probe:
            row = self.conn.execute(
                """
                SELECT lgd_district_code, similarity(district_name, %s) AS sim
                FROM gold.dim_geography
                WHERE grain = 'district' AND is_current AND lgd_state_code = %s
                ORDER BY sim DESC LIMIT 1
                """,
                (probe, state_code),
            ).fetchone()
            if row and row[1] is not None and row[1] >= 0.85:
                district_code, sim = row
                self._learn_alias(observed_state or "", observed_district or probe, state_code, district_code, float(sim))
                return Resolution(state_code, district_code, "fuzzy", float(sim), is_fuzzy=True)

        # Step 6: quarantine (caller writes the quarantine row with full raw context)
        return Resolution(state_code, None, "unresolved", 0.0)

    def _learn_alias(self, observed_state: str, observed_district: str, lgd_state_code: int, lgd_district_code: int, confidence: float) -> None:
        self.conn.execute(
            """
            INSERT INTO silver.geography_alias
                (observed_state, observed_district, lgd_state_code, lgd_district_code, match_method, confidence)
            VALUES (%s, %s, %s, %s, 'fuzzy', %s)
            ON CONFLICT (observed_state, COALESCE(observed_district, '')) DO NOTHING
            """,
            (observed_state, observed_district, lgd_state_code, lgd_district_code, confidence),
        )
        key = (normalise(observed_state), normalise(observed_district))
        self._alias_index[key] = (lgd_state_code, lgd_district_code)
