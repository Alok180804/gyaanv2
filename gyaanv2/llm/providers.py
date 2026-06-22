import requests

NO_DATA='No data found.'
SYSTEM='You answer only from the provided context. If the context does not contain the answer, return exactly: No data found. Include citations only from provided chunk labels.'

class LLM:
    def __init__(self, settings): self.s=settings

    def _setting(self, name, default=None):
        return getattr(self.s, name, default)

    def answer(self, question:str, contexts:list[dict])->str:
        if not contexts: return NO_DATA

        provider=(self._setting('llm_provider', 'ollama') or 'ollama').lower()
        prompt=self._prompt(question, contexts)

        try:
            if provider=='openai': answer=self._openai(prompt)
            elif provider=='claude': answer=self._claude(prompt)
            elif provider=='gemini': answer=self._gemini(prompt)
            elif provider=='ollama': answer=self._ollama(prompt)
            else:
                provider='extractive'
                answer=self._extractive(contexts)
        except Exception as e:
            return f'{NO_DATA}\n\nLLM error ({self._model_label(provider)}): {e}'

        return self._with_answer_metadata(answer, contexts, provider)

    def _prompt(self,q,ctx):
        blocks='\n\n'.join(f"[{i+1}] {c['citation']}\n{c['content']}" for i,c in enumerate(ctx))
        return f'{SYSTEM}\n\nContext:\n{blocks}\n\nQuestion: {q}\nAnswer with citations:'

    def _model_name(self, provider):
        configured=self._setting('llm_model')
        if configured: return configured
        defaults={
            'openai':'gpt-4o-mini',
            'claude':'claude-3-5-haiku-latest',
            'gemini':'gemini-1.5-flash',
            'ollama':'llama3.1',
            'extractive':'extractive-fallback',
        }
        return defaults.get(provider, provider)

    def _model_label(self, provider):
        return f"{provider}:{self._model_name(provider)}"

    def _with_answer_metadata(self, answer, ctx, provider):
        answer=(answer or '').strip()
        if not answer or answer==NO_DATA:
            return NO_DATA
        parts=[answer]
        if 'citation' not in answer.lower():
            citations=[]
            for c in ctx:
                citation=c.get('citation')
                if citation and citation not in citations:
                    citations.append(citation)
            if citations:
                parts.append('Citations:\n' + '\n'.join(f'- {c}' for c in citations))
        if 'model used' not in answer.lower():
            parts.append(f'Model used: {self._model_label(provider)}')
        return '\n\n'.join(parts)

    def _extractive(self,ctx):
        top=ctx[0]
        return f"{top['content'][:1200]}\n\nCitations:\n- {top['citation']}"

    def _openai(self,p):
        from openai import OpenAI
        r=OpenAI(api_key=self._setting('openai_api_key')).chat.completions.create(
            model=self._model_name('openai'),
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
            model=self._model_name('claude'),
            max_tokens=800,
            temperature=0,
            system=SYSTEM,
            messages=[{'role':'user','content':p}]
        )
        return ''.join(b.text for b in r.content if getattr(b,'type','')=='text').strip()

    def _gemini(self,p):
        from google import genai
        r=genai.Client(api_key=self._setting('google_api_key')).models.generate_content(
            model=self._model_name('gemini'),
            contents=p
        )
        return r.text.strip()

    def _ollama(self,p):
        base_url=self._setting('ollama_base_url', 'http://localhost:11434')
        model=self._model_name('ollama')
        r=requests.post(
            f'{base_url}/api/generate',
            json={'model':model,'prompt':p,'stream':False},
            timeout=120
        )
        r.raise_for_status()
        return r.json().get('response','').strip()