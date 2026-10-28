"""Strings shared by the minimal Streamlit demo."""
TRANSLATIONS = {
    "en": {
        "language": "Language / 語言", "articles": "My Articles", "create": "Create New Article",
        "topic_prompt": "Enter the topic you want to learn in depth:", "research": "Research",
        "empty": "The topic cannot be empty.", "too_long": "The topic is too long (maximum 125 characters, 240 UTF-8 bytes and 20 words).",
        "invalid": "The topic contains invalid characters or an unsafe filename.",
        "researching": "Researching the topic. This may take several minutes.", "research_done": "Research complete!",
        "writing": "Writing the article from collected information. This may take several minutes.",
        "writing_done": "Article complete!", "show_article": "Show final article", "error": "Research failed. Check your configuration and try again.",
        "back": "Select another article", "page_size": "Page size", "page": "Page", "page_count": "Page {current} of {total}",
        "my_article": "My Article", "start": "Get started", "first_research": "Start your first research!",
        "toc": "Table of contents", "references": "References", "select_reference": "Select a reference",
        "reference": "Reference [{index}]", "title": "Title", "url": "URL", "highlights": "Highlights", "no_references": "No references available",
        "perspective": "Perspective {index}", "conversation": "View the research conversations", "perspectives_start": "Identifying research perspectives.",
        "perspectives_done": "Research perspectives:\n- {perspectives}", "browse_start": "Searching the web.",
        "browsed": "Browsed: {url}", "gather_done": "Information collected.", "outline_start": "Organizing the research outline.",
        "direct_done": "Initial outline complete.", "outline_done": "Research outline complete.",
        "config_error": "Set STORM_PROVIDER, STORM_MODEL and the required API keys before starting research.",
    },
    "zh-TW": {
        "language": "Language / 語言", "articles": "我的文章", "create": "建立文章",
        "topic_prompt": "輸入想深入了解的主題：", "research": "開始研究",
        "empty": "請輸入研究主題。", "too_long": "主題過長（最多 125 個字元、240 個 UTF-8 位元組及 20 個詞）。",
        "invalid": "主題包含不允許的字元或無法使用的檔案名稱。",
        "researching": "正在研究主題，可能需要數分鐘。", "research_done": "研究完成！",
        "writing": "正在根據收集的資料撰寫文章，可能需要數分鐘。", "writing_done": "文章已完成！", "show_article": "查看完整文章",
        "error": "研究失敗，請檢查設定後重試。", "back": "選擇其他文章", "page_size": "每頁筆數", "page": "頁碼",
        "page_count": "第 {current} 頁，共 {total} 頁", "my_article": "我的文章", "start": "開始使用", "first_research": "開始第一次研究！",
        "toc": "目錄", "references": "參考資料", "select_reference": "選擇參考資料", "reference": "參考資料 [{index}]",
        "title": "標題", "url": "網址", "highlights": "摘要", "no_references": "沒有可用的參考資料",
        "perspective": "觀點 {index}", "conversation": "查看研究對話", "perspectives_start": "正在尋找研究觀點。", "perspectives_done": "研究觀點：\n- {perspectives}",
        "browse_start": "正在搜尋網路資料。", "browsed": "已瀏覽：{url}", "gather_done": "資料收集完成。",
        "outline_start": "正在整理研究大綱。", "direct_done": "初步大綱已完成。", "outline_done": "研究大綱已完成。",
        "config_error": "開始研究前，請設定 STORM_PROVIDER、STORM_MODEL 與必要的 API Key。",
    },
}


def translate(key, language="zh-TW", **values):
    return TRANSLATIONS.get(language, TRANSLATIONS["zh-TW"])[key].format(**values)
