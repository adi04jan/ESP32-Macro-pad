import json
import os

class TemplatesManager:
    def __init__(self, custom_file="macropad_templates.json", default_file="macropad_default_templates.json"):
        self.custom_file = custom_file
        self.default_file = default_file
        self.custom_templates = {}
        self.default_templates = {}
        self.load()

    def load(self):
        try:
            with open(self.default_file, 'r', encoding='utf-8') as f:
                self.default_templates = json.load(f)
        except:
            self.default_templates = {}
            
        try:
            with open(self.custom_file, 'r', encoding='utf-8') as f:
                self.custom_templates = json.load(f)
        except:
            self.custom_templates = {}

    def save(self):
        try:
            with open(self.custom_file, 'w', encoding='utf-8') as f:
                json.dump(self.custom_templates, f, indent=4)
        except Exception as e:
            print("Error saving templates:", e)

    def get_context_shortcuts(self, context):
        context_lower = context.lower()
        combined = []
        seen_desc = set()
        
        def add_from_dict(d, ctx):
            if ctx in d:
                for s in d[ctx]:
                    desc = s.get("description", "").lower()
                    if desc not in seen_desc:
                        combined.append(s)
                        seen_desc.add(desc)
                        
        add_from_dict(self.custom_templates, context_lower)
        add_from_dict(self.default_templates, context_lower)
        
        if not combined:
            for key in self.custom_templates:
                if key in context_lower or context_lower in key:
                    add_from_dict(self.custom_templates, key)
                    break
            for key in self.default_templates:
                if key in context_lower or context_lower in key:
                    add_from_dict(self.default_templates, key)
                    break
                    
        return combined

    def add_shortcuts(self, context, new_shortcuts):
        context_lower = context.lower()
        if context_lower not in self.custom_templates:
            self.custom_templates[context_lower] = []
        
        existing_desc = {s["description"].lower() for s in self.get_context_shortcuts(context_lower)}
        
        added = False
        for s in new_shortcuts:
            if s["description"].lower() not in existing_desc:
                self.custom_templates[context_lower].append(s)
                existing_desc.add(s["description"].lower())
                added = True
                
        if added:
            self.save()
