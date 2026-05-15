"""Terminal UI for interacting with the ReAct agent.

Usage:
    uv run python tui.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from app.core.agent.loop import AgentLoop
from app.core.tools import create_tool_registry
from app.services.llm.service import LLMService
from app.services.memory import MemoryService

logging.getLogger("markdown_it").setLevel(logging.WARNING)


class ConversationLogger:
    """Log complete conversations including all LLM calls and tool executions."""

    def __init__(self) -> None:
        self.log_dir = Path("logs/conversations")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.current_file = self.log_dir / f"conversation-{self.conversation_id}.jsonl"
        self._current_turn: dict[str, Any] | None = None
        self._pending_turns: list[dict[str, Any]] = []
        self._write_buffer_size = 1

    def start_turn(self, user_input: str) -> None:
        """Start a new conversation turn."""
        self._current_turn = {
            "conversation_id": self.conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "llm_calls": [],
            "tool_calls": [],
            "messages_history": [],
            "final_answer": None,
        }

    def log_llm_call(
        self,
        messages: list[dict[str, Any]],
        response: dict[str, Any],
        step: int | None = None,
    ) -> int:
        """Log a single LLM API call (input and output). Returns the call index."""
        if self._current_turn is None:
            return -1
        call_index = len(self._current_turn["llm_calls"])
        llm_entry = {
            "call_index": call_index,
            "step": step,
            "messages": messages,
            "response": {
                "content": response.get("content"),
                "tool_calls": response.get("tool_calls", []),
                "finish_reason": response.get("finish_reason"),
            },
            "tool_results": [],
        }
        self._current_turn["llm_calls"].append(llm_entry)
        return call_index

    def log_tool_call(
        self,
        tool_name: str,
        arguments: str | dict,
        result: str,
        llm_call_index: int | None = None,
    ) -> None:
        """Log a tool execution and optionally associate with an LLM call."""
        if self._current_turn is None:
            return
        truncated_result = result[:10000] if len(result) > 10000 else result
        tool_entry = {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": truncated_result,
            "llm_call_index": llm_call_index,
        }
        self._current_turn["tool_calls"].append(tool_entry)
        if llm_call_index is not None and 0 <= llm_call_index < len(self._current_turn["llm_calls"]):
            self._current_turn["llm_calls"][llm_call_index]["tool_results"].append(tool_entry)

    def update_messages_history(self, messages: list[dict[str, Any]]) -> None:
        """Update the messages history for the current turn."""
        if self._current_turn is not None:
            self._current_turn["messages_history"] = messages

    def log_error(self, error: str, context: str | None = None) -> None:
        """Log an error or warning event."""
        if self._current_turn is None:
            return
        entry = {"timestamp": datetime.now().isoformat(), "error": error}
        if context:
            entry["context"] = context
        self._current_turn.setdefault("errors", []).append(entry)

    def end_turn(self, final_answer: str | None = None) -> None:
        """End the current turn and write to file."""
        if self._current_turn is None:
            return
        self._current_turn["final_answer"] = final_answer
        self._current_turn["completed_at"] = datetime.now().isoformat()
        self._current_turn["total_llm_calls"] = len(self._current_turn["llm_calls"])
        self._current_turn["total_tool_calls"] = len(self._current_turn["tool_calls"])
        self._current_turn["total_errors"] = len(self._current_turn.get("errors", []))
        self._flush_turn()
        if final_answer and self._current_turn:
            self._save_output_file(final_answer, self._current_turn.get("user_input", ""))

    def _save_output_file(self, content: str, user_input: str) -> None:
        """Save final answer as a Markdown file."""
        import re
        output_dir = Path("logs/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[\\/:*?\"<>|]", "", user_input)
        safe_name = safe_name[:30] if safe_name else "output"
        output_file = output_dir / f"{self.conversation_id}_{safe_name}.md"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
            self._last_output_file = str(output_file)
        except IOError:
            pass

    def get_last_output_file(self) -> str | None:
        return getattr(self, "_last_output_file", None)

    def _flush_turn(self) -> None:
        """Write pending turns to file."""
        if self._current_turn is not None:
            self._pending_turns.append(self._current_turn)
        if len(self._pending_turns) >= self._write_buffer_size:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Flush write buffer to file."""
        if not self._pending_turns:
            return
        try:
            with open(self.current_file, "a", encoding="utf-8") as f:
                for turn in self._pending_turns:
                    f.write(json.dumps(turn, indent=2, ensure_ascii=False) + "\n")
            self._pending_turns = []
        except IOError as e:
            import sys
            print(f"[ERROR] Failed to write conversation log: {e}", file=sys.stderr)

    def flush(self) -> None:
        """Force flush any pending data."""
        self._flush_buffer()

    def get_log_file(self) -> Path:
        """Get the current log file path."""
        return self.current_file


_PLANNER_PROMPT = (Path(__file__).resolve().parent / "app" / "core" / "prompts" / "planner.md").read_text(encoding="utf-8")


class AgentTUI:
    """Interactive TUI for the ReAct agent."""

    def __init__(self) -> None:
        self.console = Console()
        self.memory_service = MemoryService()
        self.llm_service = LLMService()
        self.tools = create_tool_registry()
        self.conv_logger = ConversationLogger()
        self._streaming = False
        self.agent = AgentLoop(
            llm=self.llm_service,
            tools=self.tools,
            memory=self.memory_service,
            system_prompt=_PLANNER_PROMPT,
        )

    async def _process_stream(self, user_input: str, history: list[dict[str, Any]]) -> str | None:
        """Process user input using the agent stream. Returns final answer."""
        self.conv_logger.start_turn(user_input)

        self.console.print("\n[bold cyan]Assistant:[/bold cyan]")

        current_llm_call_idx = None

        async for event in self.agent.run_stream(history):
            if event["type"] == "llm_call":
                current_llm_call_idx = self.conv_logger.log_llm_call(
                    event["messages"],
                    event["response"],
                    event["step"],
                )

            elif event["type"] == "thinking":
                self.console.print(f"  [dim]Step {event['step']}[/dim]")
                self.console.print(f"  [yellow]-> Calling tool:[/yellow] [magenta]{event['tool']}[/magenta]")

            elif event["type"] == "tool_result":
                display = event["result"][:500] + "..." if len(event["result"]) > 500 else event["result"]
                self.console.print(f"  [green]OK {event['tool']}:[/green] [dim]{display}[/dim]")
                self.conv_logger.log_tool_call(
                    event["tool"],
                    event.get("arguments", ""),
                    event["result"],
                    current_llm_call_idx,
                )

            elif event["type"] == "answer":
                self.console.print()
                self.console.print(Panel(Markdown(event["content"]), title="Answer", border_style="green"))
                self.conv_logger.end_turn(final_answer=event["content"])
                return event["content"]

            elif event["type"] == "error":
                self.console.print(f"[bold red]Error:[/bold red] {event['message']}")
                self.conv_logger.log_error(event["message"], context="agent_stream")
                self.conv_logger.end_turn(final_answer=None)
        return None

    async def _process_normal(self, user_input: str, history: list[dict[str, Any]]) -> str | None:
        """Process user input using the normal (non-streaming) agent. Returns final answer."""
        self.conv_logger.start_turn(user_input)

        self.console.print("\n[cyan]Processing...[/cyan]")

        with self.console.status("[cyan]Agent is thinking...", spinner="dots"):
            state = await self.agent.run(history)

        for tc in state.tool_calls:
            self.conv_logger.log_tool_call(tc.tool_name, tc.arguments, tc.result)

        if state.final_answer:
            self.console.print()
            self.console.print(Panel(Markdown(state.final_answer), title="Answer", border_style="green"))
            output_file = self.conv_logger.get_last_output_file()
            if output_file:
                self.console.print(f"[dim]Saved to: {output_file}[/dim]")

        self.conv_logger.end_turn(final_answer=state.final_answer)

        if state.step >= self.agent._max_steps:
            self.console.print(f"\n[yellow]Note: Max steps ({self.agent._max_steps}) reached.[/yellow]")

        return state.final_answer

    def _show_welcome(self) -> None:
        """Display welcome message and help."""
        mode = "ON" if self._streaming else "OFF"
        welcome = f"""
[bold cyan]🎒 Tour Agent TUI[/bold cyan]

[bold]Commands:[/bold]
  /help    - Show this help message
  /quit    - Exit the program  
  /clear   - Clear the screen
  /stream  - Toggle streaming mode (current: [bold]{mode}[/bold])
  /tools   - List available tools
  /history - Show conversation history

[bold]Tips:[/bold]
  Type your question and press Enter to chat
  The agent will use tools when needed
  Watch the thinking process in real-time!
"""
        self.console.print(Panel(welcome, title="Tour Agent", border_style="cyan", expand=False))

    def _show_tools(self) -> None:
        """Display available tools."""
        table = Table(title="Available Tools", show_header=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")

        tools = self.tools.get_all()
        if not tools:
            self.console.print("[yellow]No tools registered.[/yellow]")
            return

        for tool in tools:
            table.add_row(tool.name, tool.description)

        self.console.print(table)

    def _show_history(self, messages: list[dict[str, Any]]) -> None:
        """Display conversation history."""
        if not messages:
            self.console.print("[yellow]No conversation history yet.[/yellow]")
            return

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                self.console.print(f"\n[bold green]You:[/bold green] {content}")
            elif role == "assistant":
                if msg.get("tool_calls"):
                    tools = [tc["function"]["name"] for tc in msg["tool_calls"]]
                    self.console.print(f"[bold cyan]Assistant:[/bold cyan] [yellow]Tools: {', '.join(tools)}[/yellow]")
                else:
                    self.console.print(f"[bold cyan]Assistant:[/bold cyan] {content[:200]}...")
            elif role == "tool":
                self.console.print(f"[dim]  [Tool result]: {content[:100]}...[/dim]")

    async def run(self) -> None:
        """Run the interactive TUI."""
        await self.memory_service.initialize()

        self.console.clear()
        self._show_welcome()
        tool_names = [t.name for t in self.tools.get_all()]
        self.console.print(f"[dim]Registered tools: {', '.join(tool_names)}[/dim]")

        messages: list[dict[str, Any]] = []
        self._streaming = False

        while True:
            try:
                self.console.print("\n[bold green]You >[/bold green] ", end="")
                user_input = input()

                if not user_input.strip():
                    continue

                cmd = user_input.strip().lower()

                if cmd in ["/quit", "/exit", "/q"]:
                    self.console.print("\n[cyan]Goodbye! 👋[/cyan]")
                    break

                elif cmd == "/help":
                    self._show_welcome()

                elif cmd == "/clear":
                    self.console.clear()
                    self._show_welcome()

                elif cmd == "/stream":
                    self._streaming = not self._streaming
                    mode = "ON" if self._streaming else "OFF"
                    self.console.print(f"[cyan]Streaming mode: [bold]{mode}[/bold][/cyan]")

                elif cmd == "/tools":
                    self._show_tools()

                elif cmd == "/history":
                    self._show_history(messages)

                else:
                    messages.append({"role": "user", "content": user_input})

                    try:
                        if self._streaming:
                            answer = await self._process_stream(user_input, messages)
                        else:
                            answer = await self._process_normal(user_input, messages)
                        if answer:
                            messages.append({"role": "assistant", "content": answer})
                    except Exception as e:
                        self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        self.conv_logger.log_error(str(e), context="agent_run")
                        self.conv_logger.end_turn(final_answer=None)
                        self.console.print(f"[yellow]Log saved to: {self.conv_logger.get_log_file()}[/yellow]")

            except (KeyboardInterrupt, EOFError):
                self.console.print(f"\n\n[cyan]Interrupted. Log saved to: {self.conv_logger.get_log_file()}[/cyan]")
                break


async def main() -> None:
    """Main entry point."""
    tui = AgentTUI()
    await tui.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)