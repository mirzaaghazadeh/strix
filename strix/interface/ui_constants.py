"""UI constants for interactive menu applications."""

from textual.binding import Binding


# CSS for InteractiveMenuApp
MENU_CSS = """
Screen {
    align: center middle;
    background: #1a1a1a;
}

#menu-container {
    width: 90;
    height: auto;
    border: solid #22c55e;
    padding: 2;
    background: #1a1a1a;
}

#menu-title {
    text-align: center;
    color: #22c55e;
    text-style: bold;
    margin-bottom: 1;
}

#menu-subtitle {
    text-align: center;
    color: #d4d4d4;
    margin-bottom: 2;
}

#menu-options {
    height: auto;
    margin: 1;
}

.menu-item {
    padding: 0 1;
    margin: 0;
    height: 1;
}

.menu-item.selected {
    background: #262626;
}

#menu-description {
    text-align: left;
    padding: 1;
    margin-top: 2;
    border-top: solid #22c55e;
    color: #a8a29e;
    height: 3;
}

#menu-footer {
    text-align: center;
    padding: 1;
    margin-top: 1;
    color: #a8a29e;
}
"""

# CSS for InputPromptApp
INPUT_CSS = """
Screen {
    align: center middle;
    background: #1a1a1a;
}

#input-container {
    width: 80;
    height: auto;
    border: solid #22c55e;
    padding: 2;
    background: #1a1a1a;
}

#input-title {
    text-align: center;
    color: #22c55e;
    text-style: bold;
    margin-bottom: 1;
}

#input-label {
    text-align: left;
    color: #d4d4d4;
    margin-bottom: 1;
    margin-top: 1;
}

#input-field {
    width: 100%;
    margin-bottom: 1;
}

#input-description {
    text-align: left;
    padding: 1;
    margin-top: 1;
    border-top: solid #22c55e;
    color: #a8a29e;
    height: 2;
}

#input-footer {
    text-align: center;
    padding: 1;
    margin-top: 1;
    color: #a8a29e;
}
"""

# CSS for ConfigurationApp
CONFIG_CSS = """
Screen {
    align: center middle;
    background: #1a1a1a;
}

#config-container {
    width: 90;
    height: auto;
    border: solid #22c55e;
    padding: 2;
    background: #1a1a1a;
}

#config-title {
    text-align: center;
    color: #22c55e;
    text-style: bold;
    margin-bottom: 1;
}

#config-subtitle {
    text-align: center;
    color: #d4d4d4;
    margin-bottom: 2;
}

.config-field {
    margin: 1 0;
}

.config-label {
    color: #d4d4d4;
    margin-bottom: 1;
}

.config-input {
    width: 100%;
    margin-bottom: 1;
}

.config-description {
    color: #a8a29e;
    margin-top: 1;
    margin-bottom: 1;
}

#config-footer {
    text-align: center;
    padding: 1;
    margin-top: 2;
    border-top: solid #22c55e;
    color: #a8a29e;
}
"""

# Key bindings for InteractiveMenuApp
BINDINGS_MENU = [
    Binding("up", "move_up", "Move Up", priority=True),
    Binding("down", "move_down", "Move Down", priority=True),
    Binding("enter", "select", "Select", priority=True),
    Binding("q", "quit", "Quit", priority=True),
    Binding("escape", "quit", "Quit", priority=True),
]

# Key bindings for InputPromptApp
BINDINGS_INPUT = [
    Binding("escape", "quit", "Quit", priority=True),
]

# Key bindings for ConfigurationApp
BINDINGS_CONFIG = [
    Binding("escape", "quit", "Back to Menu", priority=True),
    Binding("ctrl+s", "save", "Save", priority=True),
    Binding("up", "move_up", "Move Up", priority=True),
    Binding("down", "move_down", "Move Down", priority=True),
]
