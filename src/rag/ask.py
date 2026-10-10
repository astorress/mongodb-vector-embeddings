import argparse
import os

from rag import config
from rag.search import add_search_arguments, print_results, reference, search

SYSTEM_PROMPT = """Eres un experto en Don Quijote de la Mancha. Respondes preguntas sobre la obra usando \
únicamente los fragmentos que se te entregan en <fragmentos>.

- Cita cada afirmación con el número del fragmento entre corchetes, por ejemplo [2].
- Si los fragmentos no bastan para responder, dilo claramente en vez de completar con conocimiento propio.
- Responde en español, de forma breve y clara."""


def build_prompt(question, results):
    sources = "\n\n".join(
        f'<fragmento numero="{rank}" referencia="{reference(document)}" capitulo="{document["chapter_title"]}">\n'
        f"{document['text']}\n</fragmento>" for rank, document in enumerate(results, start=1))
    return f"<fragmentos>\n{sources}\n</fragmentos>\n\nPregunta: {question}"


def has_anthropic_credentials():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def generate_answer(prompt):
    import anthropic

    client = anthropic.Anthropic()
    # fallbacks="default": if the model declines on a safety classifier, the API retries on a fallback model
    with client.beta.messages.stream(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        message = stream.get_final_message()
    print()
    if message.stop_reason == "refusal":
        print("\n(El modelo rechazó responder esta pregunta.)")
    elif message.stop_reason == "max_tokens":
        print("\n(Respuesta truncada por max_tokens.)")


def main():
    parser = argparse.ArgumentParser(description="RAG sobre Don Quijote: recupera fragmentos y responde con Claude.")
    add_search_arguments(parser)
    parser.add_argument("--no-llm", action="store_true", help="solo recupera y muestra el prompt, sin llamar a Claude")
    parser.add_argument("--show-prompt", action="store_true")
    parser.set_defaults(mode="hybrid")
    args = parser.parse_args()

    results = search(args.query, args.mode, args.k, args.volume, args.chapter)
    print(f"=== 1. Recuperación ({args.mode}, k={args.k}) ===")
    print_results(results)

    prompt = build_prompt(args.query, results)
    use_llm = not args.no_llm and has_anthropic_credentials()
    if args.show_prompt or not use_llm:
        print("\n=== 2. Prompt aumentado ===\n")
        print(prompt)
    if not use_llm:
        if not args.no_llm:
            print("\n(Sin ANTHROPIC_API_KEY: crea .envs/anthropic.env para generar la respuesta con Claude.)")
        return

    print(f"\n=== 3. Respuesta ({config.CLAUDE_MODEL}) ===\n")
    generate_answer(prompt)


if __name__ == "__main__":
    main()
