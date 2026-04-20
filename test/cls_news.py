import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import akshare as ak


# ================= 配置部分 =================
st.set_page_config(
    page_title="AI 财经新闻概念挖掘终端",
    page_icon="📰",
    layout="wide"
)


# ================= 数据获取层 =================
def get_news_data():
    return ak.stock_info_global_cls()


def app():
    # ================= 界面布局 =================
    st.title("🤖 AI 新闻概念与个股挖掘")

    api_key = 'XXXXX'


    # ================= 主程序逻辑 =================
    # 加载数据
    news_df = get_news_data()

    # 初始化 Session State 用于存储选中的新闻
    if 'selected_idx' not in st.session_state:
        st.session_state.selected_idx = 0

    # 布局：左侧新闻列表，右侧详情与分析
    col_list, col_detail = st.columns([3, 7])

    with col_list:
        st.subheader("📰 实时新闻流")

        # 显示新闻列表
        for idx, row in news_df.iterrows():
            # 简单的卡片样式
            with st.container():
                # 高亮选中项
                border_color = "#2563eb" if idx == st.session_state.selected_idx else "#e2e8f0"

                # 点击事件
                if st.button(
                        f"**{row['标题']}**\n\n`{row['发布日期']} {row['发布时间']}`",
                        key=f"news_{idx}",
                        use_container_width=True,
                        help="点击查看分析"
                ):
                    st.session_state.selected_idx = idx
                    st.rerun()  # 重新运行以更新右侧视图

                st.markdown(f"<div style='border-bottom: 2px solid {border_color}; margin-bottom: 10px;'></div>",
                            unsafe_allow_html=True)

    with col_detail:
        # 获取当前选中的新闻
        current_news = news_df.iloc[st.session_state.selected_idx]

        st.markdown("---")
        # 1. 展示新闻原文
        st.subheader(f"📌 {current_news['标题']}")
        st.caption(f"发布时间：{current_news['发布日期']} {current_news['发布时间']}")
        st.info(current_news['内容'])

        # 2. AI 分析按钮
        st.markdown("### 🧠 AI 深度分析")

        if st.button("✨ 开始分析：提取概念 & 挖掘个股", type="primary", use_container_width=True):

            with st.spinner("GLM-4-Flash 正在阅读新闻并进行逻辑推理..."):
                try:
                    # 初始化 LLM
                    llm = ChatOpenAI(
                        api_key=api_key,
                        base_url="https://open.bigmodel.cn/api/paas/v4/",
                        model="glm-4-flash",
                        temperature=0.3  # 降低温度以获得更精确的分析
                    )

                    # 构建 Prompt
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", "你是一位专业的财经证券分析师。请阅读用户提供的财经新闻，完成以下任务：\n"
                                   "1. **概念识别**：分析该新闻涉及的核心产业链概念（例如：Robotaxi, CPO, 创新药等）。\n"
                                   "2. **个股挖掘**：根据概念，列出3-5只A股或港股中最相关的龙头个股名称，并用一句话解释关联理由。\n\n"
                                   "输出格式请使用 Markdown，清晰分级。"),
                        ("user", "新闻标题：{title}\n\n新闻内容：{content}\n\n请开始分析。")
                    ])

                    chain = prompt | llm | StrOutputParser()

                    # 调用模型
                    analysis_result = chain.invoke({
                        "title": current_news['标题'],
                        "content": current_news['内容']
                    })

                    # 展示结果
                    st.success("分析完成！")
                    st.markdown(analysis_result)

                    # 为了方便用户复制
                    with st.expander("查看原始输出 JSON"):
                        st.text(analysis_result)

                except Exception as e:
                    st.error(f"分析过程出错: {e}")
                    st.error("请检查 API Key 或网络连接。")


if __name__ == "__main__":
    #st.set_page_config(layout="wide")
    app()