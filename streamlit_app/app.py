"""CoHabitant app shell with cold-start authentication and RBAC."""

import logging
import streamlit as st
from utils.db import execute_transaction, run_query, get_roommate_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="CoHabitant",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def initialize_session_state():
    """Initialize auth and compatibility session values."""
    if "logged_in_user_id" not in st.session_state:
        st.session_state.logged_in_user_id = None
    if "logged_in_role" not in st.session_state:
        st.session_state.logged_in_role = None
    if "logged_in_name" not in st.session_state:
        st.session_state.logged_in_name = None
    if "logged_in_tenant_id" not in st.session_state:
        st.session_state.logged_in_tenant_id = None
    if "logged_in_tenant_name" not in st.session_state:
        st.session_state.logged_in_tenant_name = None

def hide_sidebar_for_prelogin():
    """Hide sidebar and collapsed control when user is not authenticated."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )

def clear_login_state():
    """Clear session auth data and rerun."""
    for key in ["logged_in_user_id", "logged_in_role", "logged_in_name", "logged_in_tenant_id", "logged_in_tenant_name"]:
        st.session_state[key] = None
    st.rerun()

def load_people_for_login():
    """Load all registered users for login selection."""
    sql = """
    SELECT Person_ID, First_Name, Last_Name, Email, Phone_Number
    FROM dbo.PERSON
    ORDER BY First_Name ASC, Last_Name ASC
    """
    return run_query(sql)

def get_user_role(person_id: int):
    """Return Tenant, Landlord, or None for a person ID."""
    sql = """
    SELECT
        CASE
            WHEN EXISTS (SELECT 1 FROM dbo.LANDLORD l WHERE l.Landlord_ID = p.Person_ID) THEN 'Landlord'
            WHEN EXISTS (SELECT 1 FROM dbo.TENANT t WHERE t.Tenant_ID = p.Person_ID) THEN 'Tenant'
            ELSE NULL
        END AS UserRole
    FROM dbo.PERSON p
    WHERE p.Person_ID = ?
    """
    role_df = run_query(sql, [person_id])
    if role_df.empty:
        return None
    return role_df.iloc[0]["UserRole"]

def render_register_tab():
    """Render registration form and persist new users."""
    st.subheader("Create an account")
    with st.form("registration_form"):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name")
            email = st.text_input("Email")
        with col2:
            last_name = st.text_input("Last Name")
            phone = st.text_input("Phone")

        role = st.radio("Role", ["Landlord", "Tenant"], horizontal=True)
        submitted = st.form_submit_button("Register")

        if submitted:
            if not first_name.strip() or not last_name.strip() or not email.strip():
                st.error("First Name, Last Name, and Email are required.")
                return

            try:
                # 1. Insert into PERSON
                insert_person_sql = """
                INSERT INTO dbo.PERSON (First_Name, Last_Name, Email, Phone_Number)
                VALUES (?, ?, ?, ?)
                """
                execute_transaction(insert_person_sql, [first_name.strip(), last_name.strip(), email.strip(), phone.strip() or None])

                # 2. Get the new ID
                person_df = run_query("SELECT TOP 1 Person_ID FROM dbo.PERSON WHERE Email = ? ORDER BY Person_ID DESC", [email.strip()])
                if person_df.empty:
                    st.error("Registration failed: unable to resolve new user ID.")
                    return
                
                person_id = int(person_df.iloc[0]["Person_ID"])

                # 3. Insert into Role Table
                if role == "Landlord":
                    execute_transaction("INSERT INTO dbo.LANDLORD (Landlord_ID) VALUES (?)", [person_id])
                else:
                    execute_transaction("INSERT INTO dbo.TENANT (Tenant_ID) VALUES (?)", [person_id])
                
                st.success(f"✅ Registration successful! Please switch to the Login tab to sign in as {first_name}.")
                import time
                time.sleep(2)
                st.rerun()
            except Exception as exc:
                st.error(f"Registration failed: {exc}")
                logger.error("Registration error: %s", exc)

def render_login_tab():
    """Render login form and set authenticated session values."""
    st.subheader("Sign in")
    try:
        people_df = load_people_for_login()
    except Exception as exc:
        st.error(f"Could not load users: {exc}")
        return

    if people_df.empty:
        st.info("No users found. Please register first.")
        return

    login_options = {f"{row['First_Name']} {row['Last_Name']} ({row['Email']})": int(row["Person_ID"]) for _, row in people_df.iterrows()}

    with st.form("login_form"):
        selected_user = st.selectbox("Select account", list(login_options.keys()))
        do_login = st.form_submit_button("Log In", type="primary")

        if do_login:
            person_id = login_options[selected_user]
            try:
                role = get_user_role(person_id)
                if not role:
                    st.error("Selected user does not have a valid role profile.")
                    return

                # Get the name directly from the selectbox string
                full_name = selected_user.split(" (")[0]

                # Set global session state
                st.session_state.logged_in_user_id = person_id
                st.session_state.logged_in_role = role
                st.session_state.logged_in_name = full_name

                # Set tenant compatibility state
                if role == "Tenant":
                    st.session_state.logged_in_tenant_id = person_id
                    st.session_state.logged_in_tenant_name = full_name
                
                st.rerun()

            except Exception as exc:
                st.error(f"Login failed: {exc}")

def render_prelogin_view():
    """Render centered login/register tabs while sidebar is hidden."""
    hide_sidebar_for_prelogin()
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.title("🏠 CoHabitant")
        st.caption("Shared-living operations platform")
        login_tab, register_tab = st.tabs(["Login", "Register"])
        with login_tab:
            render_login_tab()
        with register_tab:
            render_register_tab()

def render_postlogin_sidebar():
    """Render authenticated sidebar controls."""
    st.sidebar.title("🏠 CoHabitant")
    st.sidebar.markdown(f"👤 **{st.session_state.logged_in_name}**")
    st.sidebar.markdown(f"*{st.session_state.logged_in_role}*")
    st.sidebar.markdown("---")
    if st.sidebar.button("🔐 Log Out"):
        clear_login_state()

def render_tenant_onboarding():
    """Render cold start onboarding form for tenants without an active lease."""
    st.info("🏠 **Welcome to CoHabitant!** You don't have an active lease yet. Let's get you set up.")
    
    with st.form("tenant_onboarding_form", clear_on_submit=True):
        st.subheader("Join Your House")
        
        col1, col2 = st.columns(2)
        with col1:
            property_code = st.text_input("Property Invite Code", help="Provided by your landlord (corresponds to the Property ID)")
        with col2:
            monthly_rent = st.number_input("Monthly Rent ($)", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        
        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("Lease Start Date")
        with col4:
            end_date = st.date_input("Lease End Date")
        
        submitted = st.form_submit_button("Join House")
        
        if submitted:
            # Validation
            if not property_code.strip():
                st.error("Property Invite Code is required.")
                return
            
            if end_date <= start_date:
                st.error("End Date must be later than Start Date.")
                return
            
            try:
                # Convert property code to property ID
                property_id = int(property_code)
                tenant_id = st.session_state.logged_in_user_id
                
                # UPDATED: Matches your actual schema columns
                insert_sql = """
                INSERT INTO dbo.LEASE_AGREEMENT (
                    Property_ID,
                    Tenant_ID,
                    Start_Date,
                    End_Date,
                    Move_In_Date
                )
                VALUES (?, ?, ?, ?, ?)
                """
                execute_transaction(
                    insert_sql,
                    [property_id, tenant_id, start_date, end_date, start_date]
                )
                st.success(f"✅ Lease created successfully! Redirecting...")
                logger.info("Lease created for tenant %s on property %s", tenant_id, property_id)
                st.rerun()
            except ValueError:
                st.error("Property Invite Code must be a valid number.")
            except Exception as exc:
                st.error(f"Failed to create lease: {exc}")
                logger.error("Lease creation failed: %s", exc)


def render_postlogin_home():
    """Render role-aware post-login landing view."""
    st.title("CoHabitant Dashboard")
    st.write(f"Welcome, **{st.session_state.logged_in_name}**!")

    role = st.session_state.logged_in_role
    if role == "Landlord":
        st.success("Landlord access granted. Navigate the sidebar to manage your properties and leases.")
        try:
            tenants_cnt = run_query("SELECT COUNT(*) AS Cnt FROM dbo.TENANT")
            props_cnt = run_query("SELECT COUNT(*) AS Cnt FROM dbo.PROPERTY")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Registered Tenants", int(tenants_cnt.iloc[0]["Cnt"]) if not tenants_cnt.empty else 0)
            with col2:
                st.metric("Total Properties", int(props_cnt.iloc[0]["Cnt"]) if not props_cnt.empty else 0)
        except Exception as exc:
            st.warning("Could not load landlord metrics.")

    elif role == "Tenant":
        tenant_id = st.session_state.logged_in_user_id
        
        # Cold start check: Do tenants have an active lease?
        try:
            lease_count_df = run_query("SELECT COUNT(*) AS Cnt FROM dbo.LEASE_AGREEMENT WHERE Tenant_ID = ?", [tenant_id])
            lease_count = int(lease_count_df.iloc[0]["Cnt"]) if not lease_count_df.empty else 0
        except Exception as exc:
            st.warning("Could not check lease status.")
            lease_count = 0
        
        # If no lease, show onboarding
        if lease_count == 0:
            render_tenant_onboarding()
            return
        
        # Otherwise, show normal dashboard
        st.success("Tenant access granted. Use the sidebar to manage your house.")
        try:
            roommate_ids = get_roommate_ids(tenant_id)
            if not roommate_ids:
                roommate_ids = [tenant_id]

            placeholders = ", ".join("?" for _ in roommate_ids)
            bal_df = run_query("SELECT Current_Net_Balance FROM dbo.TENANT WHERE Tenant_ID = ?", [tenant_id])
            chores_df = run_query(
                f"""
                SELECT COUNT(*) AS Cnt
                FROM dbo.CHORE_ASSIGNMENT
                WHERE Assigned_Tenant_ID IN ({placeholders})
                  AND Status = 'Pending'
                """,
                roommate_ids,
            )
            props_df = run_query(
                f"""
                SELECT COUNT(*) AS Cnt
                FROM dbo.PROPOSAL
                WHERE Status = 'Active'
                  AND Proposed_By_Tenant_ID IN ({placeholders})
                """,
                roommate_ids,
            )

            balance = bal_df.iloc[0]["Current_Net_Balance"] if not bal_df.empty else 0.00
            pending_chores = int(chores_df.iloc[0]["Cnt"]) if not chores_df.empty else 0
            active_props = int(props_df.iloc[0]["Cnt"]) if not props_df.empty else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💰 Your Balance", f"${balance:,.2f}")
            with col2:
                st.metric("🧹 Pending Chores", pending_chores)
            with col3:
                st.metric("🗳️ Active Proposals", active_props)
        except Exception as exc:
            st.warning("Could not load tenant metrics.")

def main():
    """App entrypoint."""
    initialize_session_state()

    if st.session_state.logged_in_user_id is None:
        render_prelogin_view()
        return

    render_postlogin_sidebar()
    render_postlogin_home()

if __name__ == "__main__":
    main()