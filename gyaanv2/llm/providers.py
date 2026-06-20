import requests

NO_DATA='No data found.'
SYSTEM='You answer only from the provided context. If the context does not contain the answer, return exactly: No data found. Include citations only from provided chunk labels.'

class LLM:
    def __init__(self, settings): self.s=settings

    def _setting(self, name, default=None):
        return getattr(self.s, name, default)

    def answer(self, question:str, contexts:list[dict])->str:
        if not contexts: return NO_DATA

        provider=(self._setting('llm_provider', 'extractive') or 'extractive').lower()
        prompt=self._prompt(question, contexts)

        try:
            if provider=='openai': return self._openai(prompt)
            if provider=='claude': return self._claude(prompt)
            if provider=='gemini': return self._gemini(prompt)
            if provider=='ollama': return self._ollama(prompt)
        except Exception as e:
            return f'{NO_DATA}\n\nLLM error: {e}'

        return self._extractive(contexts)

    def _prompt(self,q,ctx):
        blocks='\n\n'.join(f"[{i+1}] {c['citation']}\n{c['content']}" for i,c in enumerate(ctx))
        return f'{SYSTEM}\n\nContext:\n{blocks}\n\nQuestion: {q}\nAnswer with citations:'

    def _extractive(self,ctx):
        top=ctx[0]
        return f"{top['content'][:1200]}\n\nCitations:\n- {top['citation']}"

    def _openai(self,p):
        from openai import OpenAI
        r=OpenAI(api_key=self._setting('openai_api_key')).chat.completions.create(
            model=self._setting('llm_model') or 'gpt-4o-mini',
            messages=[
                {'role':'system','content':SYSTEM},
                {'role':'user','content':p}
            ],
            temperature=0
        )
        return r.choices[0].message.content.strip()

    def _claude(self,p):
        import anthropic
        r=anthropic.Anthropic(api_key=self._setting('anthropic_api_key')).messages.create(
            model=self._setting('llm_model') or 'claude-3-5-haiku-latest',
            max_tokens=800,
            temperature=0,
            system=SYSTEM,
            messages=[{'role':'user','content':p}]
        )
        return ''.join(b.text for b in r.content if getattr(b,'type','')=='text').strip()

    def _gemini(self,p):
        from google import genai
        r=genai.Client(api_key=self._setting('google_api_key')).models.generate_content(
            model=self._setting('llm_model') or 'gemini-1.5-flash',
            contents=p
        )
        return r.text.strip()

    def _ollama(self,p):
        base_url=self._setting('ollama_base_url', 'http://localhost:11434')
        model=self._setting('llm_model') or 'llama3.1'
        r=requests.post(
            f'{base_url}/api/generate',
            json={'model':model,'prompt':p,'stream':False},
            timeout=120
        )
        r.raise_for_status()
        return r.json().get('response','').strip()