# STORM Minimal User Interface

This is a minimal user interface for `STORMWikiRunner` which includes the following features:
1. Allowing user to create a new article through the "Create New Article" page.
2. Showing the intermediate steps of STORMWikiRunner in real-time when creating an article.
3. Displaying the written article and references side by side.
4. Allowing user to view previously created articles through the "My Articles" page.

<p align="center">
  <img src="assets/create_article.jpg" style="width: 70%; height: auto;">
</p>

<p align="center">
  <img src="assets/article_display.jpg" style="width: 70%; height: auto;">
</p>

## Setup
1. Make sure you have installed `knowledge-storm` or set up the source code correctly.
2. Install additional packages required by the user interface:
    ```bash
    pip install -r requirements.txt
    ```
3. Set `STORM_PROVIDER`, `STORM_MODEL`, your provider's API key (for example `OPENAI_API_KEY`), and `YDC_API_KEY` in the environment. Do not commit API keys.
4. From the repository root, run `python -m streamlit run frontend/demo_light/storm.py`.

See [README.zh-TW.md](../../README.zh-TW.md) for Windows and macOS instructions, costs, and limitations. The interface defaults to Traditional Chinese and offers an English switch. Output is saved in `frontend/demo_light/DEMO_WORKING_DIR`.

## Customization

You can customize the `STORMWikiRunner` powering the user interface according to [the guidelines](https://github.com/stanford-oval/storm?tab=readme-ov-file#customize-storm) in the main README file.

The `STORMWikiRunner` is initialized in `set_storm_runner()` in [demo_util.py](demo_util.py). You can change `STORMWikiRunnerArguments`, `STORMWikiLMConfigs`, or use a different retrieval model according to your need.
