"""
Authentication middleware for CoHabitant Streamlit pages.

Phase 3 Upgrade: Replaces the copy-pasted check_authenticated(),
check_tenant_authenticated(), and check_landlord_authenticated()
functions that appeared in every page module.

Usage in any page file:

    from utils.auth import auth_gate
    auth_gate()              # any logged-in user
    auth_gate("Tenant")      # tenant-only pages
    auth_gate("Landlord")    # landlord-only pages
"""

from __future__ import annotations

import streamlit as st


def auth_gate(required_role: str | None = None) -> None:
    """
    Enforce authentication and optional role-based access control.

    Call at the top of every Streamlit page's main() function. If the
    check fails, the page renders an error/warning and st.stop() halts
    further execution — no content below the gate is ever rendered.

    Args:
        required_role:
            None      → any authenticated user (Tenant or Landlord)
            "Tenant"  → only users with logged_in_role == "Tenant"
            "Landlord"→ only users with logged_in_role == "Landlord"

    Side effects:
        - Calls st.stop() on failure (page rendering halts)
        - For tenant pages, also verifies logged_in_tenant_id is set
    """
    # ── Step 1: Is anyone logged in at all? ──
    user_id = st.session_state.get("logged_in_user_id")
    if user_id is None:
        st.warning("⚠️ Please log in from the main page first.")
        st.stop()

    # ── Step 2: If no specific role required, we're done ──
    if required_role is None:
        return

    # ── Step 3: Role-specific enforcement ──
    current_role = st.session_state.get("logged_in_role")

    if required_role == "Tenant":
        # Tenant pages need both the role AND the tenant_id compatibility key
        if current_role != "Tenant":
            st.error("🔒 Access denied. This page is restricted to Tenants.")
            st.stop()
        if st.session_state.get("logged_in_tenant_id") is None:
            st.error("🔒 Tenant session is invalid. Please log out and log back in.")
            st.stop()

    elif required_role == "Landlord":
        if current_role != "Landlord":
            st.error("🔒 Access denied. This page is restricted to Landlords.")
            st.stop()

    else:
        # Defensive: unknown role string passed by developer
        st.error(f"🔒 Unknown required role: '{required_role}'. Contact support.")
        st.stop()
