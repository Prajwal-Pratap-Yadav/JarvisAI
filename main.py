import ollama
from rich.console import Console

console = Console()

def chat(message):
    console.print(f"\n[bold cyan]You:[/bold cyan] {message}")
    
    response = ollama.chat(
        model="phi3:mini",
        messages=[{"role": "user", "content": message}]
    )
    
    reply = response["message"]["content"]
    console.print(f"\n[bold green]Jarvis:[/bold green] {reply}\n")
    return reply

def main():
    console.print("[bold magenta]Jarvis AI - Starting...[/bold magenta]")
    console.print("Type 'quit' to exit\n")
    
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["quit", "exit", "q"]:
            console.print("[yellow]Jarvis shutting down.[/yellow]")
            break
        if user_input:
            chat(user_input)

if __name__ == "__main__":
    main()