"""
Centralized session state management for CoHabitant.

Phase 3 Upgrade: Replaces scattered st.session_state["key"] access with
a typed, self-documenting AppState class. This prevents typo-based bugs,
provides IDE autocompletion, and makes the full set of session variables
discoverable in one place.

Usage:
    from utils.state import AppState

    state = AppState()          # reads from st.session_state (creates defaults if missing)
    state.user_id               # int | None
    state.role                  # str | None  ("Tenant" | "Landlord")
    state.tenant_id             # int | None  (set only for Tenant role)
    state.is_authenticated      # bool property
    state.is_tenant             # bool property
    state.is_landlord           # bool property
    state.clear()               # wipes all auth keys and triggers rerun
"""

from __future__ import annotations

import streamlit as st


# All session keys managed by AppState, with their default values.
_AUTH_KEYS: dict[str, object] = {
    "logged_in_user_id": None,
    "logged_in_role": None,
    "logged_in_name": None,
    "logged_in_tenant_id": None,
    "logged_in_tenant_name": None,
}


class AppState:
    """
    Typed wrapper around st.session_state for CoHabitant auth fields.

    Reads and writes go directly to st.session_state — this class adds
    no extra storage. It simply provides attribute access, type hints,
    convenience properties, and initialization-on-first-access semantics.
    """

    def __init__(self) -> None:
        """Ensure all auth keys exist in session state with defaults."""
        for key, default in _AUTH_KEYS.items():
            if key not in st.session_state:
                st.session_state[key] = default

    # ── Core auth fields (read/write) ──

    @property
    def user_id(self) -> int | None:
        return st.session_state.get("logged_in_user_id")

    @user_id.setter
    def user_id(self, value: int | None) -> None:
        st.session_state["logged_in_user_id"] = value

    @property
    def role(self) -> str | None:
        return st.session_state.get("logged_in_role")

    @role.setter
    def role(self, value: str | None) -> None:
        st.session_state["logged_in_role"] = value

    @property
    def name(self) -> str | None:
        return st.session_state.get("logged_in_name")

    @name.setter
    def name(self, value: str | None) -> None:
        st.session_state["logged_in_name"] = value

    @property
    def tenant_id(self) -> int | None:
        return st.session_state.get("logged_in_tenant_id")

    @tenant_id.setter
    def tenant_id(self, value: int | None) -> None:
        st.session_state["logged_in_tenant_id"] = value

    @property
    def tenant_name(self) -> str | None:
        return st.session_state.get("logged_in_tenant_name")

    @tenant_name.setter
    def tenant_name(self, value: str | None) -> None:
        st.session_state["logged_in_tenant_name"] = value

    # ── Convenience boolean properties ──

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_tenant(self) -> bool:
        return self.role == "Tenant" and self.tenant_id is not None

    @property
    def is_landlord(self) -> bool:
        return self.role == "Landlord"

    # ── Lifecycle methods ──

    def login(
        self,
        person_id: int,
        role: str,
        full_name: str,
    ) -> None:
        """Set all auth state for a successful login."""
        self.user_id = person_id
        self.role = role
        self.name = full_name

        if role == "Tenant":
            self.tenant_id = person_id
            self.tenant_name = full_name
        else:
            self.tenant_id = None
            self.tenant_name = None

    def clear(self) -> None:
        """Wipe all auth state and trigger a page rerun."""
        for key, default in _AUTH_KEYS.items():
            st.session_state[key] = default
        st.rerun()
