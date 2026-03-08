import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Personal Wealth Manager", layout="wide")

# --- Google Sheets Connection ---
@st.cache_resource
def get_gspread_client():
    # This securely loads your credentials from Streamlit Secrets
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(credentials)

client = get_gspread_client()

# Open your specific Google Sheet using the exact ID
SHEET_KEY = "1CZ8TuICOL-whIeh7UTdfjIX_XG6RZ_SCdIPKz0TkAc8"
try:
    sheet = client.open_by_key(SHEET_KEY)
    balances_ws = sheet.worksheet("Balances")
    transactions_ws = sheet.worksheet("Transactions")
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"Could not find the Google Sheet named '{SHEET_NAME}'. Did you share it with the service account email?")
    st.stop()

# --- Data Handling Functions ---
def load_data():
    # Read Balances
    bal_data = balances_ws.get_all_records() # Assumes headers: Fund, Balance
    funds = {row['Fund']: float(row['Balance']) for row in bal_data}
    
    # Read Transactions
    trans_data = transactions_ws.get_all_records()
    
    return {"funds": funds, "transactions": trans_data}

def save_balances(data):
    # Prepare data for the Balances tab
    cells = []
    # Assuming your Google sheet has rows 2-5 for the 4 funds
    # Order matters here based on how you set up your sheet
    row = 2
    for fund_name, balance in data['funds'].items():
        cells.append(gspread.Cell(row, 2, balance)) # Updating column B
        row += 1
    balances_ws.update_cells(cells)

def log_transaction(data, t_type, amount, source_fund, dest_fund, description):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Update local state
    new_transaction = {
        "Date": timestamp,
        "Type": t_type,
        "Amount": amount,
        "From": source_fund,
        "To": dest_fund,
        "Description": description
    }
    data['transactions'].append(new_transaction)
    
    # Update Google Sheets
    save_balances(data) # Save the new math
    
    # Append the new row to the Transactions tab
    new_row = [timestamp, t_type, amount, source_fund, dest_fund, description]
    transactions_ws.append_row(new_row)

# Initialize data state
data = load_data()

# ... [The rest of your Streamlit UI code goes here, completely unchanged!] ...

# --- UI Header & Sidebar (Dashboard) ---
st.title("📊 Nightly Financial Tracker")

st.sidebar.header("💰 Current Balances")
col1, col2 = st.sidebar.columns(2)
col1.metric("Main Vault", f"₹{data['funds']['Main Vault']:,.2f}")
col2.metric("Emergency Fund", f"₹{data['funds']['Emergency Fund']:,.2f}")
col3, col4 = st.sidebar.columns(2)
col3.metric("Fixed Expense", f"₹{data['funds']['Fixed Expense']:,.2f}")
col4.metric("Monthly Allowance", f"₹{data['funds']['Monthly Allowance']:,.2f}")

if data['funds']['Monthly Allowance'] < 0:
    st.sidebar.error("⚠️ ALERT: Monthly Allowance is overdrawn! Pull from Emergency Fund.")
if data['funds']['Fixed Expense'] < 0:
    st.sidebar.error("⚠️ ALERT: Fixed Expense fund is overdrawn!")

# --- Main Interface Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["💵 Log Income", "💸 Log Expense", "🔄 Fund Transfers", "📜 Ledger", "📅 Month End"])

# TAB 1: LOG INCOME
with tab1:
    st.subheader("Route New Income to Main Vault")
    income_source = st.selectbox("Income Source", [
        "Graphicxa Private Limited", 
        "Novanode Analytics", 
        "NA Fashion Store", 
        "YouTube (F2P Sayeed Ali)", 
        "Freelance Web Dev/Data Science", 
        "Other"
    ])
    if income_source == "Other":
        income_source = st.text_input("Specify Source")
    
    income_amount = st.number_input("Amount (₹)", min_value=0.0, step=100.0, key="inc_amt")
    
    if st.button("Log Income"):
        if income_amount > 0:
            data['funds']['Main Vault'] += income_amount
            log_transaction(data, "Income", income_amount, "External", "Main Vault", income_source)
            st.success(f"Successfully added ₹{income_amount} to Main Vault!")
            st.rerun()

# TAB 2: LOG EXPENSE
with tab2:
    st.subheader("Record Daily Spending")
    expense_fund = st.radio("Deduct from which fund?", ["Monthly Allowance", "Fixed Expense"])
    
    if expense_fund == "Fixed Expense":
        expense_desc = st.selectbox("Category", ["Hosting (nagraphics.in/graphicxa.online)", "BCA Tuition/Materials", "Software Subs", "Other"])
    else:
        expense_desc = st.selectbox("Category", ["Cricket Gear (XI Stars)", "KingShot", "Food & Dining", "Personal", "Other"])
        
    if expense_desc == "Other":
        expense_desc = st.text_input("Specify Expense")
        
    expense_amount = st.number_input("Amount (₹)", min_value=0.0, step=100.0, key="exp_amt")
    
    if st.button("Log Expense"):
        if expense_amount > 0:
            data['funds'][expense_fund] -= expense_amount
            log_transaction(data, "Expense", expense_amount, expense_fund, "External", expense_desc)
            st.success(f"Logged ₹{expense_amount} expense from {expense_fund}.")
            st.rerun()

# TAB 3: TRANSFERS & EMERGENCY PULLS
with tab3:
    st.subheader("Internal Fund Routing")
    trans_from = st.selectbox("From", ["Main Vault", "Emergency Fund"])
    
    if trans_from == "Main Vault":
        trans_to = st.selectbox("To", ["Fixed Expense", "Monthly Allowance", "Emergency Fund"])
    else:
        trans_to = st.selectbox("To", ["Monthly Allowance", "Fixed Expense"])
        
    trans_amount = st.number_input("Transfer Amount (₹)", min_value=0.0, step=100.0, key="trans_amt")
    trans_reason = st.text_input("Reason (Optional)")
    
    if st.button("Execute Transfer"):
        if trans_amount > 0 and data['funds'][trans_from] >= trans_amount:
            data['funds'][trans_from] -= trans_amount
            data['funds'][trans_to] += trans_amount
            desc = f"Transfer: {trans_reason}" if trans_reason else "Internal Routing"
            log_transaction(data, "Transfer", trans_amount, trans_from, trans_to, desc)
            st.success(f"Transferred ₹{trans_amount} from {trans_from} to {trans_to}.")
            st.rerun()
        elif data['funds'][trans_from] < trans_amount:
            st.error(f"Insufficient funds in {trans_from}!")

# TAB 4: LEDGER VIEW
with tab4:
    st.subheader("Transaction History")
    if data['transactions']:
        df = pd.DataFrame(data['transactions'])
        st.dataframe(df.iloc[::-1], use_container_width=True)
    else:
        st.info("No transactions logged yet.")

# TAB 5: MONTH END ROLLOVER
with tab5:
    st.subheader("End of Month Sweep")
    st.markdown("Run this on the last day of the month. It takes any unspent money from your Allowance and Fixed Expenses and sweeps it back into the Main Vault for next month's planning.")
    
    allowance_bal = data['funds']['Monthly Allowance']
    fixed_bal = data['funds']['Fixed Expense']
    total_sweep = max(0, allowance_bal) + max(0, fixed_bal)
    
    st.info(f"Total available to sweep back to Main Vault: ₹{total_sweep:,.2f}")
    
    if st.button("Execute Monthly Rollover"):
        if allowance_bal > 0:
            data['funds']['Main Vault'] += allowance_bal
            data['funds']['Monthly Allowance'] = 0.0
            log_transaction(data, "Rollover", allowance_bal, "Monthly Allowance", "Main Vault", "End of Month Sweep")
            
        if fixed_bal > 0:
            data['funds']['Main Vault'] += fixed_bal
            data['funds']['Fixed Expense'] = 0.0
            log_transaction(data, "Rollover", fixed_bal, "Fixed Expense", "Main Vault", "End of Month Sweep")
            
        if total_sweep > 0:
            st.success(f"Successfully swept ₹{total_sweep:,.2f} into the Main Vault. Your active funds are reset to zero.")
            st.rerun()
        else:
            st.warning("No positive balances left to sweep!")
