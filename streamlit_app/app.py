"""
CoHabitant - Intelligent Roommate Management Application
Main routing page with session state management.

This is the entry point for the multi-page Streamlit app.
All page navigation and user session management is handled here.
"""

import streamlit as st
import logging
from utils.db import get_active_tenants, get_tenant_name, run_query    

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="🏠 CoHabitant",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main { padding: 0rem 1rem; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 16px; }
    .user-badge { 
        background-color: #FF6B6B; 
        color: white; 
        padding: 10px 15px; 
        border-radius: 5px; 
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables on app startup."""
    if "logged_in_tenant_id" not in st.session_state:
        st.session_state.logged_in_tenant_id = None
    if "logged_in_tenant_name" not in st.session_state:
        st.session_state.logged_in_tenant_name = None


def render_sidebar():
    """Render sidebar with user login simulation and navigation."""
    st.sidebar.title("🏠 CoHabitant")
    st.sidebar.markdown("---")
    
    # Login simulation section
    st.sidebar.subheader("👤 User Login")
    
    try:
        tenants_df = get_active_tenants()
        
        if tenants_df.empty:
            st.sidebar.warning("⚠️ No tenants found in database")
            return None
        
        # Create a display string combining name and ID
        tenant_options = {
            f"{row['Full_Name']} (ID: {row['Tenant_ID']})": row['Tenant_ID']
            for _, row in tenants_df.iterrows()
        }
        
        selected_tenant = st.sidebar.selectbox(
            "Select your account:",
            options=list(tenant_options.keys()),
            index=0
        )
        
        if selected_tenant:
            tenant_id = tenant_options[selected_tenant]
            logging_in = st.sidebar.button("🔓 Log In", key="login_btn")
            
            if logging_in:
                st.session_state.logged_in_tenant_id = tenant_id
                st.session_state.logged_in_tenant_name = selected_tenant.split(" (ID:")[0]
                st.success(f"✅ Logged in as {st.session_state.logged_in_tenant_name}")
    
    except Exception as e:
        st.sidebar.error(f"❌ Error loading tenants: {e}")
        logger.error(f"Failed to load tenants: {e}")
        return None
    
    st.sidebar.markdown("---")
    
    # Display current user
    if st.session_state.logged_in_tenant_id:
        st.sidebar.markdown(f"""
        <div class="user-badge">
        👤 Logged in as: {st.session_state.logged_in_tenant_name}
        </div>
        """, unsafe_allow_html=True)
        
        if st.sidebar.button("🔐 Log Out", key="logout_btn"):
            st.session_state.logged_in_tenant_id = None
            st.session_state.logged_in_tenant_name = None
            st.rerun()
    else:
        st.sidebar.warning("⚠️ Please log in to continue")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📌 Navigation**")
    st.sidebar.markdown("""
    - 💸 Financials
    - 🧹 Chores (Coming Soon)
    - 🗳️ House Voting (Coming Soon)
    - 📈 Analytics (Coming Soon)
    """)


def main():
    """Main app entry point."""
    initialize_session_state()
    render_sidebar()
    
    # Main content area
    if st.session_state.logged_in_tenant_id is None:
        st.title("🏠 CoHabitant")
        st.markdown("""
        ## Welcome to CoHabitant
        
        Your intelligent roommate management system for shared living.
        
        **Features:**
        - 💸 **Smart Expense Splitting** - Track and split household expenses fairly
        - 🧹 **Chore Management** - Assign and verify chore completion
        - 🗳️ **Democratic Voting** - Make group decisions transparently
        - 📈 **Analytics Dashboard** - Visualize household metrics
        
        👈 **Please log in using the sidebar to get started.**
        """)
    else:
        st.title("🏠 CoHabitant Dashboard")
        st.markdown(f"Welcome back, **{st.session_state.logged_in_tenant_name}**! 👋")
        
        # --- DYNAMIC DASHBOARD DATA ---
        tenant_id = st.session_state.logged_in_tenant_id
        
        # 1. Fetch live balance
        bal_df = run_query("SELECT Current_Net_Balance FROM dbo.TENANT WHERE Tenant_ID = ?", [tenant_id])
        balance = bal_df.iloc[0]['Current_Net_Balance'] if not bal_df.empty else 0.00
        
        # 2. Fetch pending chores for this specific user
        chores_df = run_query("SELECT COUNT(*) as Cnt FROM dbo.CHORE_ASSIGNMENT WHERE Assigned_Tenant_ID = ? AND Status = 'Pending'", [tenant_id])
        pending_chores = chores_df.iloc[0]['Cnt'] if not chores_df.empty else 0
        
        # 3. Fetch total active house proposals
        props_df = run_query("SELECT COUNT(*) as Cnt FROM dbo.PROPOSAL WHERE Status = 'Active'")
        active_props = props_df.iloc[0]['Cnt'] if not props_df.empty else 0
        
        # Render the live metrics!
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Your Balance", f"${balance:,.2f}")
        with col2:
            st.metric("🧹 Pending Chores", str(pending_chores))
        with col3:
            st.metric("🗳️ Active Proposals", str(active_props))
        
        st.markdown("---")
        st.info("📌 Navigate to 💸 Financials page from the left sidebar to manage expenses and payments.")


if __name__ == "__main__":
    main()
