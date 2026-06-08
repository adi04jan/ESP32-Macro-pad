import customtkinter as ctk

class RecommendationWidget(ctk.CTkToplevel):
    def __init__(self, master, settings_callback):
        super().__init__(master)
        self.title("Macropad AI")
        self.geometry("360x300+20+20") 
        self.attributes('-topmost', 'true')
        self.overrideredirect(True) 
        self.settings_cb = settings_callback
        
        self.current_context = ""
        self.options_map = {1: [], 2: [], 3: [], 4: []}
        self.index_map = {1: 0, 2: 0, 3: 0, 4: 0}
        
        bg_color = "#252526"
        border_color = "#3c3c3c"
        header_bg = "#333333"
        text_color = "#cccccc"
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, border_width=1, border_color=border_color, fg_color=bg_color)
        self.main_frame.pack(fill="both", expand=True)
        
        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color=header_bg, corner_radius=0, height=28)
        self.top_bar.pack(fill="x")
        self.top_bar.pack_propagate(False) 
        
        self.header = ctk.CTkLabel(self.top_bar, text=" AI Context", font=ctk.CTkFont(family="Consolas", size=12), text_color=text_color)
        self.header.pack(side="left", padx=8)
        
        close_btn = ctk.CTkButton(self.top_bar, text="✕", width=28, height=28, corner_radius=0, fg_color="transparent", text_color="#aaaaaa", hover_color="#e81123", command=self.withdraw)
        close_btn.pack(side="right")
        
        settings_btn = ctk.CTkButton(self.top_bar, text="⚙", width=28, height=28, corner_radius=0, fg_color="transparent", text_color="#aaaaaa", hover_color="#555555", command=self.settings_cb)
        settings_btn.pack(side="right")
        
        self.status = ctk.CTkLabel(self.main_frame, text="", text_color="#888888", font=ctk.CTkFont(family="Consolas", size=11, slant="italic"))
        
        self.list_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=2, pady=4)
        
        self.top_bar.bind("<ButtonPress-1>", self.start_move)
        self.top_bar.bind("<B1-Motion>", self.do_move)
        
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        x = self.winfo_x() + event.x - self.x
        y = self.winfo_y() + event.y - self.y
        self.geometry(f"+{x}+{y}")

    def update_context(self, context, templates, is_generating):
        self.current_context = context
        self.header.configure(text=f" ⚡ {context}")
        
        for w in self.list_frame.winfo_children(): w.destroy()
            
        if is_generating:
            self.status.configure(text="Generating AI shortcuts...")
            self.status.pack(pady=10)
            return
            
        self.status.pack_forget()
        
        for k in range(1, 5):
            self.options_map[k] = []
            self.index_map[k] = 0
            
        for t in templates:
            knum = t.get("key_num")
            if knum and 1 <= knum <= 4:
                self.options_map[knum].append(t)
                
        for k in range(1, 5):
            self.build_key_row(k)

    def build_key_row(self, key_num):
        opts = self.options_map[key_num]
        
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(2, weight=1)
        
        lbl_key = ctk.CTkLabel(row, text=f"K{key_num}", width=30, fg_color="#444444", corner_radius=4, font=ctk.CTkFont(weight="bold", size=11))
        lbl_key.grid(row=0, column=0, padx=(4, 8), pady=2)
        
        cycle_frame = ctk.CTkFrame(row, fg_color="transparent")
        cycle_frame.grid(row=0, column=1, padx=(0, 8))
        
        btn_up = ctk.CTkButton(cycle_frame, text="▲", width=20, height=12, fg_color="#333333", text_color="#888888", hover_color="#555555",
                               command=lambda k=key_num: self.cycle_option(k, -1))
        btn_up.pack(pady=(0, 1))
        btn_down = ctk.CTkButton(cycle_frame, text="▼", width=20, height=12, fg_color="#333333", text_color="#888888", hover_color="#555555",
                                 command=lambda k=key_num: self.cycle_option(k, 1))
        btn_down.pack()
        
        desc = "No shortcut available"
        if opts:
            idx = self.index_map[key_num]
            desc = opts[idx].get("description", "Unknown")
            
        lbl_desc = ctk.CTkLabel(row, text=desc, anchor="w", font=ctk.CTkFont(size=12))
        lbl_desc.grid(row=0, column=2, sticky="we", pady=2)
        
        regen_btn = ctk.CTkButton(row, text="↻", width=24, height=24, fg_color="transparent", text_color="#aaaaaa", hover_color="#555555",
                                  command=lambda k=key_num: self.trigger_regen(k))
        regen_btn.grid(row=0, column=3, padx=4)

    def cycle_option(self, key_num, direction):
        opts = self.options_map[key_num]
        if not opts: return
        self.index_map[key_num] = (self.index_map[key_num] + direction) % len(opts)
        
        for w in self.list_frame.winfo_children(): w.destroy()
        for k in range(1, 5): self.build_key_row(k)
            
        self.push_current_selection(key_num)

    def push_current_selection(self, key_num):
        opts = self.options_map[key_num]
        if not opts: return
        t = opts[self.index_map[key_num]]
        if hasattr(self.master, "serial_worker"):
            self.master.serial_worker.push_shortcut(t)

    def trigger_regen(self, key_num):
        if hasattr(self.master, "ai_worker"):
            self.master.ai_worker.queue.put({"action": "generate_and_validate", "context": self.current_context, "key_num": key_num})
