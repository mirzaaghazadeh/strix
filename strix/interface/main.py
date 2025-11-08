#!/usr/bin/env python3
"""
Strix Agent Interface
"""

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import litellm
from docker.errors import DockerException
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Input, Static

from strix.interface.cli import run_cli
from strix.interface.tui import run_tui
from strix.interface.utils import (
    assign_workspace_subdirs,
    build_llm_stats_text,
    build_stats_text,
    check_docker_connection,
    clone_repository,
    collect_local_sources,
    generate_run_name,
    image_exists,
    infer_target_type,
    process_pull_line,
    validate_llm_response,
)
from strix.runtime.docker_runtime import STRIX_IMAGE
from strix.telemetry.tracer import get_global_tracer


logging.getLogger().setLevel(logging.ERROR)


def validate_environment() -> None:  # noqa: PLR0912, PLR0915
    console = Console()
    missing_required_vars = []
    missing_optional_vars = []

    if not os.getenv("STRIX_LLM"):
        missing_required_vars.append("STRIX_LLM")

    has_base_url = any(
        [
            os.getenv("LLM_API_BASE"),
            os.getenv("OPENAI_API_BASE"),
            os.getenv("LITELLM_BASE_URL"),
            os.getenv("OLLAMA_API_BASE"),
        ]
    )

    if not os.getenv("LLM_API_KEY"):
        if not has_base_url:
            missing_required_vars.append("LLM_API_KEY")
        else:
            missing_optional_vars.append("LLM_API_KEY")

    if not has_base_url:
        missing_optional_vars.append("LLM_API_BASE")

    if not os.getenv("PERPLEXITY_API_KEY"):
        missing_optional_vars.append("PERPLEXITY_API_KEY")

    if missing_required_vars:
        error_text = Text()
        error_text.append("❌ ", style="bold red")
        error_text.append("MISSING REQUIRED ENVIRONMENT VARIABLES", style="bold red")
        error_text.append("\n\n", style="white")

        for var in missing_required_vars:
            error_text.append(f"• {var}", style="bold yellow")
            error_text.append(" is not set\n", style="white")

        if missing_optional_vars:
            error_text.append("\nOptional environment variables:\n", style="dim white")
            for var in missing_optional_vars:
                error_text.append(f"• {var}", style="dim yellow")
                error_text.append(" is not set\n", style="dim white")

        error_text.append("\nRequired environment variables:\n", style="white")
        for var in missing_required_vars:
            if var == "STRIX_LLM":
                error_text.append("• ", style="white")
                error_text.append("STRIX_LLM", style="bold cyan")
                error_text.append(
                    " - Model name to use with litellm (e.g., 'openai/gpt-5')\n",
                    style="white",
                )
            elif var == "LLM_API_KEY":
                error_text.append("• ", style="white")
                error_text.append("LLM_API_KEY", style="bold cyan")
                error_text.append(
                    " - API key for the LLM provider (required for cloud providers)\n",
                    style="white",
                )

        if missing_optional_vars:
            error_text.append("\nOptional environment variables:\n", style="white")
            for var in missing_optional_vars:
                if var == "LLM_API_KEY":
                    error_text.append("• ", style="white")
                    error_text.append("LLM_API_KEY", style="bold cyan")
                    error_text.append(" - API key for the LLM provider\n", style="white")
                elif var == "LLM_API_BASE":
                    error_text.append("• ", style="white")
                    error_text.append("LLM_API_BASE", style="bold cyan")
                    error_text.append(
                        " - Custom API base URL if using local models (e.g., Ollama, LMStudio)\n",
                        style="white",
                    )
                elif var == "PERPLEXITY_API_KEY":
                    error_text.append("• ", style="white")
                    error_text.append("PERPLEXITY_API_KEY", style="bold cyan")
                    error_text.append(
                        " - API key for Perplexity AI web search (enables real-time research)\n",
                        style="white",
                    )

        error_text.append("\nExample setup:\n", style="white")
        error_text.append("export STRIX_LLM='openai/gpt-5'\n", style="dim white")

        if "LLM_API_KEY" in missing_required_vars:
            error_text.append("export LLM_API_KEY='your-api-key-here'\n", style="dim white")

        if missing_optional_vars:
            for var in missing_optional_vars:
                if var == "LLM_API_KEY":
                    error_text.append(
                        "export LLM_API_KEY='your-api-key-here'  # optional with local models\n",
                        style="dim white",
                    )
                elif var == "LLM_API_BASE":
                    error_text.append(
                        "export LLM_API_BASE='http://localhost:11434'  "
                        "# needed for local models only\n",
                        style="dim white",
                    )
                elif var == "PERPLEXITY_API_KEY":
                    error_text.append(
                        "export PERPLEXITY_API_KEY='your-perplexity-key-here'\n", style="dim white"
                    )

        panel = Panel(
            error_text,
            title="[bold red]🛡️  STRIX CONFIGURATION ERROR",
            title_align="center",
            border_style="red",
            padding=(1, 2),
        )

        console.print("\n")
        console.print(panel)
        console.print()
        sys.exit(1)


def check_docker_installed() -> None:
    if shutil.which("docker") is None:
        console = Console()
        error_text = Text()
        error_text.append("❌ ", style="bold red")
        error_text.append("DOCKER NOT INSTALLED", style="bold red")
        error_text.append("\n\n", style="white")
        error_text.append("The 'docker' CLI was not found in your PATH.\n", style="white")
        error_text.append(
            "Please install Docker and ensure the 'docker' command is available.\n\n", style="white"
        )

        panel = Panel(
            error_text,
            title="[bold red]🛡️  STRIX STARTUP ERROR",
            title_align="center",
            border_style="red",
            padding=(1, 2),
        )
        console.print("\n", panel, "\n")
        sys.exit(1)


async def warm_up_llm() -> None:
    console = Console()

    try:
        model_name = os.getenv("STRIX_LLM", "openai/gpt-5")
        api_key = os.getenv("LLM_API_KEY")

        if api_key:
            litellm.api_key = api_key

        api_base = (
            os.getenv("LLM_API_BASE")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("LITELLM_BASE_URL")
            or os.getenv("OLLAMA_API_BASE")
        )
        if api_base:
            litellm.api_base = api_base

        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with just 'OK'."},
        ]

        response = litellm.completion(
            model=model_name,
            messages=test_messages,
        )

        validate_llm_response(response)

    except Exception as e:  # noqa: BLE001
        error_text = Text()
        error_text.append("❌ ", style="bold red")
        error_text.append("LLM CONNECTION FAILED", style="bold red")
        error_text.append("\n\n", style="white")
        error_text.append("Could not establish connection to the language model.\n", style="white")
        error_text.append("Please check your configuration and try again.\n", style="white")
        error_text.append(f"\nError: {e}", style="dim white")

        panel = Panel(
            error_text,
            title="[bold red]🛡️  STRIX STARTUP ERROR",
            title_align="center",
            border_style="red",
            padding=(1, 2),
        )

        console.print("\n")
        console.print(panel)
        console.print()
        sys.exit(1)


class InteractiveMenuApp(App):  # type: ignore[misc]
    """Interactive BIOS-style menu app with arrow key navigation."""
    
    CSS = """
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
    
    BINDINGS = [
        Binding("up", "move_up", "Move Up", priority=True),
        Binding("down", "move_down", "Move Down", priority=True),
        Binding("enter", "select", "Select", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("escape", "quit", "Quit", priority=True),
    ]
    
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
    
    def watch_selected_index(self, selected_index: int) -> None:
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
    
    CSS = """
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
    
    BINDINGS = [
        Binding("escape", "quit", "Quit", priority=True),
    ]
    
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


async def prompt_input_async(prompt_text: str, description: str = "", allow_empty: bool = False) -> str | None:
    """Prompt for input using textual with same styling as menu."""
    app = InputPromptApp(prompt_text, description, allow_empty)
    return await app.run_async()


async def show_interactive_menu_async() -> argparse.Namespace:
    """Display an interactive menu using textual with arrow key navigation."""
    menu_options = [
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
            "example": "strix -t https://dev.your-app.com -t https://staging.your-app.com -t https://prod.your-app.com",
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Focused testing with instructions",
            "description": "Prioritize specific vulnerability types or testing approaches",
            "example": "strix --target api.your-app.com --instruction \"Prioritize authentication and authorization testing\"",
            "targets": [],
            "instruction": None,
        },
        {
            "title": "Testing with credentials",
            "description": "Test with provided credentials, focus on privilege escalation",
            "example": "strix --target https://your-app.com --instruction \"Test with credentials: testuser/testpass. Focus on privilege escalation and access control bypasses.\"",
            "targets": [],
            "instruction": None,
        },
    ]
    
    app = InteractiveMenuApp(menu_options)
    choice = await app.run_async()
    
    console = Console()
    
    if choice is None:
        console.print("\n[bold yellow]Cancelled.[/bold yellow]\n")
        sys.exit(0)
    
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
            target_description = "Example: https://github.com/org/repo or git@github.com:org/repo.git"
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


def show_interactive_menu() -> argparse.Namespace:
    """Display an interactive menu using textual with arrow key navigation."""
    return asyncio.run(show_interactive_menu_async())


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strix Multi-Agent Cybersecurity Penetration Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Web application penetration test
  strix --target https://example.com

  # GitHub repository analysis
  strix --target https://github.com/user/repo
  strix --target git@github.com:user/repo.git

  # Local code analysis
  strix --target ./my-project

  # Domain penetration test
  strix --target example.com

  # Multiple targets (e.g., white-box testing with source and deployed app)
  strix --target https://github.com/user/repo --target https://example.com
  strix --target ./my-project --target https://staging.example.com --target https://prod.example.com

  # Custom instructions
  strix --target example.com --instruction "Focus on authentication vulnerabilities"
        """,
    )

    parser.add_argument(
        "-t",
        "--target",
        type=str,
        required=False,
        action="append",
        help="Target to test (URL, repository, local directory path, or domain name). "
        "Can be specified multiple times for multi-target scans.",
    )
    parser.add_argument(
        "--instruction",
        type=str,
        help="Custom instructions for the penetration test. This can be "
        "specific vulnerability types to focus on (e.g., 'Focus on IDOR and XSS'), "
        "testing approaches (e.g., 'Perform thorough authentication testing'), "
        "test credentials (e.g., 'Use the following credentials to access the app: "
        "admin:password123'), "
        "or areas of interest (e.g., 'Check login API endpoint for security issues')",
    )

    parser.add_argument(
        "--run-name",
        type=str,
        help="Custom name for this penetration test run",
    )

    parser.add_argument(
        "-n",
        "--non-interactive",
        action="store_true",
        help=(
            "Run in non-interactive mode (no TUI, exits on completion). "
            "Default is interactive mode with TUI."
        ),
    )

    args = parser.parse_args()

    # If no targets provided, we'll show interactive menu in main()
    if not args.target:
        args.target = None
        args.targets_info = []
        return args

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
        except ValueError:
            parser.error(f"Invalid target '{target}'")

    assign_workspace_subdirs(args.targets_info)

    return args


def display_completion_message(args: argparse.Namespace, results_path: Path) -> None:
    console = Console()
    tracer = get_global_tracer()

    scan_completed = False
    if tracer and tracer.scan_results:
        scan_completed = tracer.scan_results.get("scan_completed", False)

    has_vulnerabilities = tracer and len(tracer.vulnerability_reports) > 0

    completion_text = Text()
    if scan_completed:
        completion_text.append("🦉 ", style="bold white")
        completion_text.append("AGENT FINISHED", style="bold green")
        completion_text.append(" • ", style="dim white")
        completion_text.append("Penetration test completed", style="white")
    else:
        completion_text.append("🦉 ", style="bold white")
        completion_text.append("SESSION ENDED", style="bold yellow")
        completion_text.append(" • ", style="dim white")
        completion_text.append("Penetration test interrupted by user", style="white")

    stats_text = build_stats_text(tracer)
    llm_stats_text = build_llm_stats_text(tracer)

    target_text = Text()
    if len(args.targets_info) == 1:
        target_text.append("🎯 Target: ", style="bold cyan")
        target_text.append(args.targets_info[0]["original"], style="bold white")
    else:
        target_text.append("🎯 Targets: ", style="bold cyan")
        target_text.append(f"{len(args.targets_info)} targets\n", style="bold white")
        for i, target_info in enumerate(args.targets_info):
            target_text.append("   • ", style="dim white")
            target_text.append(target_info["original"], style="white")
            if i < len(args.targets_info) - 1:
                target_text.append("\n")

    panel_parts = [completion_text, "\n\n", target_text]

    if stats_text.plain:
        panel_parts.extend(["\n", stats_text])

    if llm_stats_text.plain:
        panel_parts.extend(["\n", llm_stats_text])

    if scan_completed or has_vulnerabilities:
        results_text = Text()
        results_text.append("📊 Results Saved To: ", style="bold cyan")
        results_text.append(str(results_path), style="bold yellow")
        panel_parts.extend(["\n\n", results_text])

    panel_content = Text.assemble(*panel_parts)

    border_style = "green" if scan_completed else "yellow"

    panel = Panel(
        panel_content,
        title="[bold green]🛡️  STRIX CYBERSECURITY AGENT",
        title_align="center",
        border_style=border_style,
        padding=(1, 2),
    )

    console.print("\n")
    console.print(panel)
    console.print()


def pull_docker_image() -> None:
    console = Console()
    client = check_docker_connection()

    if image_exists(client, STRIX_IMAGE):
        return

    console.print()
    console.print(f"[bold cyan]🐳 Pulling Docker image:[/] {STRIX_IMAGE}")
    console.print("[dim yellow]This only happens on first run and may take a few minutes...[/]")
    console.print()

    with console.status("[bold cyan]Downloading image layers...", spinner="dots") as status:
        try:
            layers_info: dict[str, str] = {}
            last_update = ""

            for line in client.api.pull(STRIX_IMAGE, stream=True, decode=True):
                last_update = process_pull_line(line, layers_info, status, last_update)

        except DockerException as e:
            console.print()
            error_text = Text()
            error_text.append("❌ ", style="bold red")
            error_text.append("FAILED TO PULL IMAGE", style="bold red")
            error_text.append("\n\n", style="white")
            error_text.append(f"Could not download: {STRIX_IMAGE}\n", style="white")
            error_text.append(str(e), style="dim red")

            panel = Panel(
                error_text,
                title="[bold red]🛡️  DOCKER PULL ERROR",
                title_align="center",
                border_style="red",
                padding=(1, 2),
            )
            console.print(panel, "\n")
            sys.exit(1)

    success_text = Text()
    success_text.append("✅ ", style="bold green")
    success_text.append("Successfully pulled Docker image", style="green")
    console.print(success_text)
    console.print()


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    args = parse_arguments()

    # If no targets provided, show interactive menu
    if not args.target:
        args = show_interactive_menu()

    check_docker_installed()
    pull_docker_image()

    validate_environment()
    asyncio.run(warm_up_llm())

    if not args.run_name:
        args.run_name = generate_run_name()

    for target_info in args.targets_info:
        if target_info["type"] == "repository":
            repo_url = target_info["details"]["target_repo"]
            dest_name = target_info["details"].get("workspace_subdir")
            cloned_path = clone_repository(repo_url, args.run_name, dest_name)
            target_info["details"]["cloned_repo_path"] = cloned_path

    args.local_sources = collect_local_sources(args.targets_info)

    if args.non_interactive:
        asyncio.run(run_cli(args))
    else:
        asyncio.run(run_tui(args))

    results_path = Path("agent_runs") / args.run_name
    display_completion_message(args, results_path)

    if args.non_interactive:
        tracer = get_global_tracer()
        if tracer and tracer.vulnerability_reports:
            sys.exit(2)


if __name__ == "__main__":
    main()
