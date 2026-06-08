import json
import queue
import threading
import urllib.request
import urllib.error

class AIQueueManager:
    def __init__(self, settings, templates_mgr, log_callback, on_success_callback):
        self.settings = settings
        self.templates_mgr = templates_mgr
        self.log = log_callback
        self.on_success = on_success_callback
        
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.thread.start()

    def worker_loop(self):
        while True:
            task = self.queue.get()
            if task is None: break
            try:
                self.process_task(task)
            except Exception as e:
                self.log(f"AI Queue Error: {e}\n")
            self.queue.task_done()

    def process_task(self, task):
        action = task.get("action")
        context = task.get("context")
        key_num = task.get("key_num", None)
        
        if action == "generate_and_validate":
            self.log(f"AI: Generating for [{context}]...\n")
            raw_shortcuts = self.generate_shortcuts(context, key_num)
            if raw_shortcuts:
                self.log(f"AI: Validating shortcuts for [{context}]...\n")
                validated = self.validate_shortcuts(context, raw_shortcuts)
                if validated:
                    self.log(f"AI: Added new validated shortcuts for [{context}].\n")
                    self.templates_mgr.add_shortcuts(context, validated)
                    self.on_success(context)
                        
    def make_api_call(self, system_prompt, user_prompt):
        provider = self.settings.get("ai_provider", "Ollama (Local)")
        key = self.settings.get("ai_key", "http://localhost:11434").strip().rstrip('/')
        model = self.settings.get("ai_model", "llama3:70b").strip()
        
        debug = self.settings.get("ai_debug_enabled", False)
        if debug:
            self.log(f"\n[AI DEBUG] Provider: {provider} | Model: {model}\n")
            self.log(f"[AI DEBUG] Sys Prompt: {system_prompt[:50]}...\n")
            self.log(f"[AI DEBUG] Usr Prompt: {user_prompt}\n")
            
        result_text = ""
        try:
            if provider == "Ollama (Local)":
                model_name = model if model else "llama3"
                url = f"{key}/api/generate"
                req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"})
                payload = {"model": model_name, "prompt": f"{system_prompt}\nUser Prompt: {user_prompt}", "stream": False}
                data = json.dumps(payload).encode("utf-8")
                
                if debug:
                    self.log(f"[AI DEBUG] URL: {url}\n[AI DEBUG] Payload: {json.dumps(payload)}\n")
                    
                with urllib.request.urlopen(req, data=data, timeout=120) as response:
                    raw_res = response.read().decode()
                    if debug: self.log(f"[AI DEBUG] Raw Response: {raw_res[:200]}...\n")
                    res = json.loads(raw_res)
                    result_text = res.get("response", "")
                    
            elif provider == "Gemini":
                model_name = model if model else "gemini-1.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"})
                payload = {"contents": [{"parts": [{"text": f"{system_prompt}\nUser Prompt: {user_prompt}"}]}]}
                data = json.dumps(payload).encode("utf-8")
                
                if debug:
                    self.log(f"[AI DEBUG] URL: {url[:60]}...[HIDDEN_KEY]\n[AI DEBUG] Payload: {json.dumps(payload)}\n")
                    
                with urllib.request.urlopen(req, data=data, timeout=120) as response:
                    raw_res = response.read().decode()
                    if debug: self.log(f"[AI DEBUG] Raw Response: {raw_res[:200]}...\n")
                    res = json.loads(raw_res)
                    result_text = res["candidates"][0]["content"]["parts"][0]["text"]
                    
            elif provider == "OpenAI":
                model_name = model if model else "gpt-4o-mini"
                url = "https://api.openai.com/v1/chat/completions"
                req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
                payload = {"model": model_name, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
                data = json.dumps(payload).encode("utf-8")
                
                if debug:
                    self.log(f"[AI DEBUG] URL: {url}\n[AI DEBUG] Payload: {json.dumps(payload)}\n")
                    
                with urllib.request.urlopen(req, data=data, timeout=120) as response:
                    raw_res = response.read().decode()
                    if debug: self.log(f"[AI DEBUG] Raw Response: {raw_res[:200]}...\n")
                    res = json.loads(raw_res)
                    result_text = res["choices"][0]["message"]["content"]
                    
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8', errors='replace')
            if debug: self.log(f"\n[AI ERROR] HTTP {e.code}: {err_msg}\n")
            raise Exception(f"HTTP {e.code}: {err_msg}")
        except Exception as e:
            if debug: self.log(f"\n[AI ERROR] Exception: {str(e)}\n")
            raise e
                
        result_text = result_text.strip()
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
        return result_text

    def generate_shortcuts(self, context, key_num=None):
        valid_keys = "LEFT_CTRL, RIGHT_CTRL, LEFT_SHIFT, RIGHT_SHIFT, LEFT_ALT, ENTER, ESC, TAB, SPACE, F1-F12, A-Z, 0-9, UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW, MINUS, EQUAL, TILDE"
        system_prompt = f"""You are an advanced Macro Shortcut Generator for a developer. 
CRITICAL: Respond ONLY with a raw JSON array. DO NOT wrap the output in markdown code blocks (e.g. no ```json).
Valid keys for keycombo: {valid_keys}.
JSON Schema:
[
  {{"key_num": 1, "description": "Save File", "actions": [{{"type":"keycombo","keys":["LEFT_CTRL","S"]}}]}},
  {{"key_num": 2, "description": "Git Status", "actions": [{{"type":"text","value":"git status"}}, {{"type":"key","value":"ENTER"}}]}}
]"""

        user_prompt = f"Context: {context}.\nGenerate 4 new, unique, robust and highly productive keyboard shortcuts for this context."
        
        custom_existing = self.templates_mgr.custom_templates.get(context.lower(), [])
        if custom_existing:
            existing_desc = [s.get("description", "") for s in custom_existing][-10:]
            user_prompt += f"\n\nPersonalization Context - You already have these shortcuts: {', '.join(existing_desc)}.\nDO NOT duplicate these. Adapt your suggestions based on this workflow style."

        if key_num:
            user_prompt += f"\nSpecifically assign the generated shortcuts to key_num: {key_num}."
            
        try:
            res = self.make_api_call(system_prompt, user_prompt)
            if res.startswith("```json"): res = res[7:]
            if res.startswith("```"): res = res[3:]
            if res.endswith("```"): res = res[:-3]
            parsed = json.loads(res.strip())
            return parsed if isinstance(parsed, list) else None
        except Exception as e:
            self.log(f"Generation error: {e}\n")
            return None

    def validate_shortcuts(self, context, shortcuts):
        valid_keys = "LEFT_CTRL, RIGHT_CTRL, LEFT_SHIFT, RIGHT_SHIFT, LEFT_ALT, ENTER, ESC, TAB, SPACE, F1-F12, A-Z, 0-9, UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW, MINUS, EQUAL, TILDE"
        system_prompt = f"""You are a Validator. Ensure the JSON array is perfectly valid for Macropad actions. 
CRITICAL: Respond ONLY with a raw JSON array. DO NOT use markdown formatting.
Fix impossible key combinations. Ensure 'keys' or 'value' only use: {valid_keys}."""
        user_prompt = f"Context: {context}\nValidate and fix this JSON:\n{json.dumps(shortcuts)}"
        
        try:
            res = self.make_api_call(system_prompt, user_prompt)
            if res.startswith("```json"): res = res[7:]
            if res.startswith("```"): res = res[3:]
            if res.endswith("```"): res = res[:-3]
            parsed = json.loads(res.strip())
            return parsed if isinstance(parsed, list) else shortcuts
        except Exception as e:
            self.log(f"Validation error: {e}\n")
            return shortcuts
