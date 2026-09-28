"""Jawabdari - entry point and navigation.

Run:  streamlit run app.py

This file only sets up the top navigation bar. Each screen lives in pages/.
The url_path values keep QR-code links working: /Public_Board?work_id=W-0001
"""

import streamlit as st

pages = [
    st.Page("pages/0_Dashboard.py", title="Dashboard", icon=":material/space_dashboard:",
            url_path="Dashboard", default=True),
    st.Page("pages/1_Register_Work.py", title="Register work", icon=":material/add_road:",
            url_path="Register_Work"),
    st.Page("pages/3_Contractor_Portal.py", title="Contractor desk", icon=":material/engineering:",
            url_path="Contractor_Portal"),
    st.Page("pages/2_Report_Defect.py", title="Report a problem", icon=":material/campaign:",
            url_path="Report_Defect"),
    st.Page("pages/4_Public_Board.py", title="Public board", icon=":material/qr_code_2:",
            url_path="Public_Board"),
]

st.navigation(pages, position="top").run()
