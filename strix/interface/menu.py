"""Interactive menu applications for Strix."""

import argparse
import sys
from typing import Any

import litellm
from rich.console import Console
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Input, Static

from strix.interface.config_manager import ConfigManager
from strix.interface.ui_constants import (
    BINDINGS_CONFIG,
    BINDINGS_INPUT,
    BINDINGS_MENU,
    CONFIG_CSS,
    INPUT_CSS,
    MENU_CSS,
)
from strix.interface.utils import assign_workspace_subdirs, infer_target_type


class InteractiveMenuApp(App):  # type: ignore[misc]
    """Interactive BIOS-style menu app with arrow key navigation."""

    CSS = MENU_CSS
    BINDINGS = BINDINGS_MENU

    selected_index = reactive(0)

    def __init__(self, menu_options: list[dict[str, Any]]) -> None:
        super().__init__()
        self.menu_options = menu_options
        self.result: int | None = None
        self._menu_items: list[Static] = []
        self._description_widget: Static | None = None

    def compose(self) -> ComposeResult:
        with Container(id="menu-container"):
            yield Static("🦉 STRIX CYBERSECURITY AGENT", id="menu-title")
            yield Static("Select a usage scenario:", id="menu-subtitle")

            with Container(id="menu-options"):
                for i, option in enumerate(self.menu_options):
                    checkbox = "[x]" if i == 0 else "[ ]"
                    item = Static(
                        f"{checkbox} {i + 1}. {option['title']}",
                        classes="menu-item",
                        id=f"item-{i}",
                    )
                    self._menu_items.append(item)
                    yield item

            yield Static("", id="menu-description")
            yield Static("↑/↓: Navigate  |  Enter: Select  |  Q/Esc: Quit", id="menu-footer")

    def on_mount(self) -> None:
        """Initialize the menu."""
        self._description_widget = self.query_one("#menu-description", Static)
        self._update_selection()

    def watch_selected_index(self, _selected_index: int) -> None:
        """Update selection when index changes."""
        self._update_selection()

    def _update_selection(self) -> None:
        """Update the visual selection and description."""
        for i, item_widget in enumerate(self._menu_items):
            if i == self.selected_index:
                # Update checkbox to [x] and highlight
                item_widget.update(f"[x] {i + 1}. {self.menu_options[i]['title']}")
                item_widget.add_class("selected")
            else:
                # Update checkbox to [ ] and remove highlight
                item_widget.update(f"[ ] {i + 1}. {self.menu_options[i]['title']}")
                item_widget.remove_class("selected")

        # Update description at bottom
        if self._description_widget:
            selected = self.menu_options[self.selected_index]
            desc_text = f"{selected['description']}\nExample: {selected['example']}"
            self._description_widget.update(desc_text)

    def action_move_up(self) -> None:
        """Move selection up."""
        if self.selected_index > 0:
            self.selected_index -= 1

    def action_move_down(self) -> None:
        """Move selection down."""
        if self.selected_index < len(self.menu_options) - 1:
            self.selected_index += 1

    def action_select(self) -> None:
        """Select the current option."""
        self.result = self.selected_index + 1
        self.exit(result=self.result)

    def action_quit(self) -> None:
        """Quit the menu."""
        self.exit(result=None)


class InputPromptApp(App):  # type: ignore[misc]
    """Input prompt app with same styling as menu."""

    CSS = INPUT_CSS
    BINDINGS = BINDINGS_INPUT

    def __init__(self, prompt_text: str, description: str = "", allow_empty: bool = False) -> None:
        super().__init__()
        self.prompt_text = prompt_text
        self.description = description
        self.allow_empty = allow_empty
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="input-container"):
            yield Static("🦉 STRIX CYBERSECURITY AGENT", id="input-title")
            yield Static(self.prompt_text, id="input-label")
            yield Input(placeholder="", id="input-field")
            if self.description:
                yield Static(self.description, id="input-description")
            yield Static("Enter: Submit  |  Esc: Cancel", id="input-footer")

    def on_mount(self) -> None:
        """Focus the input field on mount."""
        input_field = self.query_one("#input-field", Input)
        input_field.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        value = event.value.strip()
        if not value and not self.allow_empty:
            return  # Don't submit empty values

        self.result = value
        self.exit(result=value)

    def action_quit(self) -> None:
        """Quit the input prompt."""
        self.exit(result=None)


class ConfigurationApp(App):  # type: ignore[misc]
    """Configuration management app."""

    CSS = CONFIG_CSS
    BINDINGS = BINDINGS_CONFIG

    def __init__(self) -> None:
        super().__init__()
        self.config_manager = ConfigManager()
        self._inputs: dict[str, Input] = {}
        self._input_order: list[str] = []

    def compose(self) -> ComposeResult:
        config = self.config_manager.get_all_config()

        with Container(id="config-container"):
            yield Static("🦉 STRIX CONFIGURATION", id="config-title")
            yield Static("Manage your Strix settings", id="config-subtitle")

            # STRIX_LLM
            yield Static("Model Name (STRIX_LLM)", classes="config-label")
            yield Static(
                "Example: openai/gpt-5, anthropic/claude-3-5-sonnet",
                classes="config-description",
            )
            llm_input = Input(
                value=config.get("STRIX_LLM", ""),
                placeholder="openai/gpt-5",
                id="strix_llm",
                classes="config-input",
            )
            self._inputs["STRIX_LLM"] = llm_input
            self._input_order.append("STRIX_LLM")
            yield llm_input

            # LLM_API_KEY
            yield Static("LLM API Key (LLM_API_KEY)", classes="config-label")
            yield Static("Your API key for the LLM provider", classes="config-description")
            api_key_input = Input(
                value=config.get("LLM_API_KEY", ""),
                placeholder="sk-...",
                password=True,
                id="llm_api_key",
                classes="config-input",
            )
            self._inputs["LLM_API_KEY"] = api_key_input
            self._input_order.append("LLM_API_KEY")
            yield api_key_input

            # PERPLEXITY_API_KEY
            yield Static("Perplexity API Key (PERPLEXITY_API_KEY)", classes="config-label")
            yield Static("Optional: For web search capabilities", classes="config-description")
            perplexity_input = Input(
                value=config.get("PERPLEXITY_API_KEY", ""),
                placeholder="pplx-...",
                password=True,
                id="perplexity_api_key",
                classes="config-input",
            )
            self._inputs["PERPLEXITY_API_KEY"] = perplexity_input
            self._input_order.append("PERPLEXITY_API_KEY")
            yield perplexity_input

            # LLM_API_BASE
            yield Static("LLM API Base URL (LLM_API_BASE)", classes="config-label")
            yield Static(
                "Optional: For local models (e.g., http://localhost:11434)",
                classes="config-description",
            )
            api_base_input = Input(
                value=config.get("LLM_API_BASE", ""),
                placeholder="http://localhost:11434",
                id="llm_api_base",
                classes="config-input",
            )
            self._inputs["LLM_API_BASE"] = api_base_input
            self._input_order.append("LLM_API_BASE")
            yield api_base_input

            yield Static("↑/↓: Navigate  |  Ctrl+S: Save  |  Esc: Back to Menu", id="config-footer")

    def on_mount(self) -> None:
        """Focus the first input on mount."""
        if self._inputs and self._input_order:
            first_key = self._input_order[0]
            self._inputs[first_key].focus()

    def _get_current_input_index(self) -> int:
        """Get the index of the currently focused input."""
        focused = self.focused
        if isinstance(focused, Input):
            for i, key in enumerate(self._input_order):
                if self._inputs[key] == focused:
                    return i
        return 0

    def action_move_up(self) -> None:
        """Move focus to the previous input."""
        current_idx = self._get_current_input_index()
        if current_idx > 0:
            prev_key = self._input_order[current_idx - 1]
            self._inputs[prev_key].focus()

    def action_move_down(self) -> None:
        """Move focus to the next input."""
        current_idx = self._get_current_input_index()
        if current_idx < len(self._input_order) - 1:
            next_key = self._input_order[current_idx + 1]
            self._inputs[next_key].focus()

    def action_save(self) -> None:
        """Save configuration."""
        updates = {}
        for key, input_widget in self._inputs.items():
            value = input_widget.value.strip()
            if value:  # Only save non-empty values
                updates[key] = value
            elif key in ["STRIX_LLM", "LLM_API_KEY"]:  # Required fields
                # Keep existing value if not changed
                existing = self.config_manager.get_value(key)
                if existing:
                    updates[key] = existing

        self.config_manager.update_config(updates)
        self.config_manager.apply_to_environment()

        # Re-apply litellm settings immediately after saving
        if updates.get("LLM_API_KEY"):
            litellm.api_key = updates["LLM_API_KEY"]
        elif "LLM_API_KEY" in updates:  # Empty value - clear it
            litellm.api_key = None

        if updates.get("LLM_API_BASE"):
            litellm.api_base = updates["LLM_API_BASE"]
        elif updates.get("OPENAI_API_BASE"):
            litellm.api_base = updates["OPENAI_API_BASE"]
        elif updates.get("LITELLM_BASE_URL"):
            litellm.api_base = updates["LITELLM_BASE_URL"]
        elif updates.get("OLLAMA_API_BASE"):
            litellm.api_base = updates["OLLAMA_API_BASE"]
        elif "LLM_API_BASE" in updates or "OPENAI_API_BASE" in updates:
            # Empty value - clear it
            litellm.api_base = None

        # Show success message
        console = Console()
        console.print("\n[bold green]✓ Configuration saved successfully![/bold green]\n")

        self.exit(result=True)

    def action_quit(self) -> None:
        """Quit without saving."""
        self.exit(result=False)


async def prompt_input_async(
    prompt_text: str, description: str = "", allow_empty: bool = False
) -> str | None:
    """Prompt for input using textual with same styling as menu."""
    app = InputPromptApp(prompt_text, description, allow_empty)
    return await app.run_async()


async def show_configuration_async() -> bool:
    """Show configuration management screen."""
    app = ConfigurationApp()
    result = await app.run_async()
    return result is True


def _get_menu_options() -> list[dict[str, Any]]:
    """Get the menu options list."""
    return [
        {
            "title": "Local codebase analysis",
            "description": "Analyze a local directory for security vulnerabilities",
            "example": "strix --target ./app-directory",
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Repository security review",
            "description": "Clone and analyze a GitHub repository",
            "example": "strix --target https://github.com/org/repo",
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Web application assessment",
            "description": "Perform penetration testing on a deployed web application",
            "example": "strix --target https://your-app.com",
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Multi-target white-box testing",
            "description": "Test source code + deployed app simultaneously",
            "example": "strix -t https://github.com/org/app -t https://your-app.com",
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Test multiple environments",
            "description": "Test dev, staging, and production environments simultaneously",
            "example": (
                "strix -t https://dev.your-app.com "
                "-t https://staging.your-app.com "
                "-t https://prod.your-app.com"
            ),
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Focused testing with instructions",
            "description": "Prioritize specific vulnerability types or testing approaches",
            "example": (
                "strix --target api.your-app.com "
                '--instruction "Prioritize authentication and authorization testing"'
            ),
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Testing with credentials",
            "description": "Test with provided credentials, focus on privilege escalation",
            "example": (
                "strix --target https://your-app.com "
                '--instruction "Test with credentials: testuser/testpass. '
                'Focus on privilege escalation and access control bypasses."'
            ),
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Configuration",
            "description": "Manage Strix settings (API keys, model, etc.)",
            "example": "Configure STRIX_LLM, LLM_API_KEY, PERPLEXITY_API_KEY",
            "targets": [],
            "instruction": None,
            "is_config": True,
        },
    ]


async def show_interactive_menu_async() -> argparse.Namespace | None:  # noqa: PLR0912, PLR0915
    """Display an interactive menu using textual with arrow key navigation."""
    menu_options = _get_menu_options()

    while True:
        app = InteractiveMenuApp(menu_options)
        choice = await app.run_async()

        if choice is None:
            return None

        # Check if configuration was selected
        if choice == 8:  # Configuration option
            await show_configuration_async()
            # Return to menu after configuration
            continue

        # Regular menu option selected
        break

    console = Console()

    if choice is None:
        console.print("\n[bold yellow]Cancelled.[/bold yellow]\n")
        sys.exit(0)

    # Get menu options again (they might have been modified)
    menu_options = _get_menu_options()
    selected_option = menu_options[choice - 1]

    # Create a namespace object with the selected option
    args = argparse.Namespace()
    args.target = None
    args.targets_info = []
    args.instruction = selected_option.get("instruction")
    args.run_name = None
    args.non_interactive = False
    args._menu_selection = selected_option

    # Prompt for target(s) based on selection using textual input
    if choice in [4, 5]:  # Multi-target scenarios
        targets = []
        while True:
            target = await prompt_input_async(
                "Enter target (empty line to finish)",
                f"Target {len(targets) + 1} of multiple targets",
                allow_empty=True,
            )
            if target is None:
                if targets:
                    break
                console.print("\n[bold yellow]Cancelled.[/bold yellow]\n")
                sys.exit(0)
            if not target:
                if targets:
                    break
                continue
            targets.append(target)
        args.target = targets
    else:
        target_prompt_text = "Enter target"
        target_description = ""
        if choice == 1:  # Local codebase
            target_prompt_text = "Enter local directory path"
            target_description = "Example: ./app-directory or /path/to/project"
        elif choice == 2:  # Repository
            target_prompt_text = "Enter repository URL"
            target_description = (
                "Example: https://github.com/org/repo or git@github.com:org/repo.git"
            )
        elif choice == 3:  # Web app
            target_prompt_text = "Enter web application URL"
            target_description = "Example: https://your-app.com or http://localhost:3000"
        elif choice == 6:  # Focused testing
            target_prompt_text = "Enter target URL"
            target_description = "Example: api.your-app.com or https://api.example.com"
        elif choice == 7:  # With credentials
            target_prompt_text = "Enter target URL"
            target_description = "Example: https://your-app.com or http://localhost:8080"

        target = await prompt_input_async(target_prompt_text, target_description)
        if target is None or not target:
            console.print("\n[bold yellow]Cancelled.[/bold yellow]\n")
            sys.exit(0)
        args.target = [target]

        # For focused testing and credentials, prompt for instruction if not set
        if choice == 6 and not args.instruction:
            instruction = await prompt_input_async(
                "Enter instructions (optional)",
                "Prioritize specific vulnerability types or testing approaches",
                allow_empty=True,
            )
            if instruction:
                args.instruction = instruction
        elif choice == 7 and not args.instruction:
            credentials = await prompt_input_async(
                "Enter credentials (format: username/password)",
                "Example: admin:password123 or testuser/testpass",
                allow_empty=True,
            )
            instruction_text = await prompt_input_async(
                "Enter additional instructions (optional)",
                "Focus on privilege escalation and access control bypasses",
                allow_empty=True,
            )
            if credentials:
                instruction_parts = [f"Test with credentials: {credentials}"]
                if instruction_text:
                    instruction_parts.append(instruction_text)
                args.instruction = ". ".join(instruction_parts) + "."
            elif instruction_text:
                args.instruction = instruction_text

    # Process targets
    args.targets_info = []
    for target in args.target:
        try:
            target_type, target_dict = infer_target_type(target)

            if target_type == "local_code":
                display_target = target_dict.get("target_path", target)
            else:
                display_target = target

            args.targets_info.append(
                {"type": target_type, "details": target_dict, "original": display_target}
            )
        except ValueError as e:
            console.print(f"[bold red]Invalid target '{target}': {e}[/bold red]\n")
            sys.exit(1)

    assign_workspace_subdirs(args.targets_info)

    return args


def show_interactive_menu() -> argparse.Namespace | None:
    """Display an interactive menu using textual with arrow key navigation."""
    import asyncio

    return asyncio.run(show_interactive_menu_async())
