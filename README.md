# Anki AI Dock

[![AnkiWeb](https://img.shields.io/badge/AnkiWeb-Coming%20Soon-blue.svg)](https://ankiweb.net/shared/info/) 
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A powerful Anki addon that integrates your favorite artificial intelligence services directly into the editor and reviewer, transforming the way you create and study your flashcards. Leverage the power of AI to generate content, translate, summarize, and much more, without ever leaving Anki!

## ✨ Key Features

*   **Seamless AI Integration:** Open a dockable webview panel within Anki's editor and reviewer, with direct access to services like Gemini, ChatGPT, Perplexity, Claude, and other customizable AI sites.
*   **Customizable Prompts:** Define your own custom prompts with placeholders (`{text}`) to quickly send selected text from Anki to the AI.
*   **Smart Paste:** Paste AI responses directly into any field of your Anki note with a simple click or shortcut.
*   **Flexible Layout:** Customize the position (right, left, above, below) and size ratio of the AI dock to fit your workflow.
*   **Integrated Zoom:** Adjust the zoom of the AI webview for optimal readability.
*   **Global Shortcuts:** Assign custom keyboard shortcuts to:
    *   Paste AI output into the desired field.
    *   Show/hide the AI dock.
    *   Activate your custom prompts with selected text.
*   **Persistent Configuration:** All your settings, prompts, and favorite AI sites are saved persistently.
*   **Context Menus:** Quickly access your custom AI prompts directly from the editor and reviewer context menus.

## 🚀 How to Use

1.  **Open the Editor or Reviewer:** The AI Dock will automatically appear as a side or bottom panel.
2.  **Select Your AI Service:** Use the dropdown menu at the top to choose the AI service you want to use (e.g., Gemini, ChatGPT).
3.  **Send Text to AI:**
    *   Select text in a field of your Anki note.
    *   Right-click and choose "AI Dock Prompts" to select one of your custom prompts.
    *   The selected text will be sent to the AI webview, formatted with the chosen prompt.
4.  **Paste from AI to Anki:**
    *   Select the desired text or HTML within the AI panel.
    *   Right-click on the AI panel and choose "Paste to Field", then select the destination field.
    *   Alternatively, use the global shortcut "Paste from AI into Field" (configurable in settings).

## ⚙️ Configuration

Access AI Dock settings via `Tools > AI Dock Settings` in Anki's main menu. Here you can:

*   **Custom Prompts:** Add, edit, or remove your custom prompts. Remember to include `{text}` in the prompt template.
*   **AI Services:** Manage the list of available AI services, adding new URLs or modifying existing ones.
*   **Global Shortcuts:** Assign or modify keyboard shortcuts for the addon's main actions.

## 📦 Installation

1.  **Download the addon:** Coming soon on AnkiWeb. For now, you can clone this repository.
2.  **Open Anki:** Go to `Tools > Add-ons > Open Add-on Folder`.
3.  **Copy the folder:** Copy the `Anki_Ai_Dock_refactor-init` folder (or the name of the downloaded addon folder) into Anki's add-on folder.
4.  **Restart Anki:** The addon will be active upon restart.

## 📸 Screenshots

*(Add appealing screenshots of the addon in action in the editor and reviewer, showing the different features and the AI panel here.)*

## 🤝 Contributions

Contributions are welcome! If you have ideas for new features, bug reports, or improvements, feel free to open an issue or a pull request.

## 📄 License

This project is released under the MIT License. See the [LICENSE](LICENSE) file for more details.