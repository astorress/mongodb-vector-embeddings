import os

from lab.config import CLAUDE_MODEL
from lab.search import reference

SYSTEM_PROMPT = """Eres un experto en Don Quijote de la Mancha. Respondes preguntas sobre la obra usando \
únicamente los fragmentos que se te entregan en <fragmentos>.

- Cita cada afirmación con el número del fragmento entre corchetes, por ejemplo [2].
- Si los fragmentos no bastan para responder, dilo claramente en vez de completar con conocimiento propio.
- Responde en español, de forma breve y clara."""


def build_prompt(question, results):
    sources = "\n\n".join(
        f'<fragmento numero="{rank}" referencia="{reference(doc)}" capitulo="{doc["chapter_title"]}">\n'
        f"{doc['text']}\n</fragmento>" for rank, doc in enumerate(results, start=1))
    return f"<fragmentos>\n{sources}\n</fragmentos>\n\nPregunta: {question}"


def has_credentials():
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def generate(prompt, system=SYSTEM_PROMPT, model=CLAUDE_MODEL, effort="medium"):
    import anthropic

    client = anthropic.Anthropic()
    # fallbacks="default": if the model declines on a safety classifier, the API retries on a fallback model
    with client.beta.messages.stream(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": effort},
            system=system,
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
    return message
