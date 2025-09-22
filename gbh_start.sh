ps aux | grep streamlit

lsof -i :8501


python -c "import streamlit; print('Streamlit版本:', streamlit.__version__)"

python -c "import tradingagents; print('TradingAgents已安装')"

pip install streamlit plotly

source env/bin/activate && pip install streamlit plotly

source env/bin/activate && python start_web.py

sleep 3 && curl -s http://localhost:8501 | head -5

