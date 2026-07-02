#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import re
from datetime import datetime
from pathlib import Path


class POTranslatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("凯普勒186F PO 翻译工具 v1.2")
        self.root.geometry("720x580")

        self.input_po_path = tk.StringVar()
        self.translations_json_path = tk.StringVar()
        self.output_po_path = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):

        title_label = tk.Label(self.root, text="凯普勒186F PO 翻译工具 v1.2", 
                               font=("Microsoft YaHei", 15, "bold"), pady=8)
        title_label.pack()

        frame_files = ttk.LabelFrame(self.root, text="文件选择", padding=10)
        frame_files.pack(fill="x", padx=15, pady=5)

        tk.Label(frame_files, text="原始 PO 文件：").grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(frame_files, textvariable=self.input_po_path, width=55).grid(row=0, column=1, padx=5)
        tk.Button(frame_files, text="选择文件", command=self.select_input_po).grid(row=0, column=2)

        tk.Label(frame_files, text="翻译结果 JSON：").grid(row=1, column=0, sticky="w", pady=3)
        tk.Entry(frame_files, textvariable=self.translations_json_path, width=55).grid(row=1, column=1, padx=5)
        tk.Button(frame_files, text="选择文件", command=self.select_translations_json).grid(row=1, column=2)

        tk.Label(frame_files, text="输出中文 PO 文件：").grid(row=2, column=0, sticky="w", pady=3)
        tk.Entry(frame_files, textvariable=self.output_po_path, width=55).grid(row=2, column=1, padx=5)
        tk.Button(frame_files, text="选择保存位置", command=self.select_output_po).grid(row=2, column=2)

        frame_buttons = ttk.Frame(self.root)
        frame_buttons.pack(fill="x", padx=15, pady=10)

        btn_style = {"width": 18, "height": 2, "font": ("Microsoft YaHei", 10)}

        tk.Button(frame_buttons, text="① 提取未翻译内容", 
                  command=self.extract_untranslated, bg="#4CAF50", fg="white", **btn_style).pack(side="left", padx=5)
        tk.Button(frame_buttons, text="② 应用翻译（推荐）", 
                  command=self.apply_translations_threaded, bg="#2196F3", fg="white", **btn_style).pack(side="left", padx=5)
        tk.Button(frame_buttons, text="查看当前进度", 
                  command=self.show_stats, bg="#FF9800", fg="white", **btn_style).pack(side="left", padx=5)

        frame_progress = ttk.LabelFrame(self.root, text="日志", padding=8)
        frame_progress.pack(fill="both", expand=True, padx=15, pady=5)

        self.progress = ttk.Progressbar(frame_progress, length=680, mode="determinate")
        self.progress.pack(pady=5)

        self.log_text = tk.Text(frame_progress, height=16, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        self.status_label = tk.Label(self.root, text="就绪", anchor="w", relief="sunken")
        self.status_label.pack(fill="x", side="bottom")

    def log(self, msg):
        self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def select_input_po(self):
        path = filedialog.askopenfilename(filetypes=[("PO files", "*.po")])
        if path:
            self.input_po_path.set(path)

    def select_translations_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            self.translations_json_path.set(path)

    def select_output_po(self):
        path = filedialog.asksaveasfilename(defaultextension=".po", filetypes=[("PO files", "*.po")])
        if path:
            self.output_po_path.set(path)

    def extract_untranslated(self):

        pass   

    def apply_translations_threaded(self):
        t = threading.Thread(target=self.apply_translations)
        t.daemon = True
        t.start()

    def apply_translations(self):
        input_po = self.input_po_path.get()
        trans_json = self.translations_json_path.get()
        output_po = self.output_po_path.get()

        if not all([input_po, trans_json, output_po]):
            messagebox.showwarning("提示", "请先选择三个文件")
            return

        try:
            self.log("开始应用翻译...")
            self.progress["value"] = 0

            entries, content = self.parse_po_file(input_po)

            with open(trans_json, "r", encoding="utf-8") as f:
                translations = json.load(f)

            # 构建翻译字典（优先用 msgid 作为 key）
            trans_dict = {}
            if isinstance(translations, list):
                for item in translations:
                    if item.get("msgstr"):
                        trans_dict[item["msgid"]] = item["msgstr"]   # 用 msgid 做 key，最可靠

            translated_count = 0
            new_content = content

            for i, entry in enumerate(entries):
                if not entry.get("needs_translation"):
                    continue

                msgid = entry["msgid"]
                if msgid in trans_dict:
                    new_msgstr = trans_dict[msgid]
                    old_block = f'msgid "{msgid}"\nmsgstr "{entry["msgstr"]}"'
                    new_block = f'msgid "{msgid}"\nmsgstr "{new_msgstr}"'

                    if old_block in new_content:
                        new_content = new_content.replace(old_block, new_block, 1)
                        translated_count += 1

                progress = int((i + 1) / len(entries) * 100)
                self.progress["value"] = progress

            new_content = self.update_po_header(new_content)

            with open(output_po, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.log(f"✅ 应用完成！成功写入 {translated_count} 条翻译")
            messagebox.showinfo("完成", f"成功应用 {translated_count} 条翻译！")

        except Exception as e:
            self.log(f"错误：{e}")
            messagebox.showerror("错误", str(e))

    def parse_po_file(self, filepath):
        entries = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        pattern = re.compile(r'msgid "(?P<msgid>(?:\\.|[^"])*)"\nmsgstr "(?P<msgstr>(?:\\.|[^"])*)"', re.MULTILINE)

        for match in pattern.finditer(content):
            msgid = match.group("msgid").replace('\\"', '"')
            msgstr = match.group("msgstr").replace('\\"', '"')
            entries.append({
                "msgid": msgid,
                "msgstr": msgstr,
                "needs_translation": (not msgstr or msgstr == msgid)
            })
        return entries, content

    def update_po_header(self, content):
        now = datetime.now().strftime("%Y-%m-%d %H:%M%z")
        content = re.sub(r'^Language: .*', 'Language: zh_CN', content, flags=re.MULTILINE)
        content = re.sub(r'^PO-Revision-Date: .*', f'PO-Revision-Date: {now}', content, flags=re.MULTILINE)
        return content

    def show_stats(self):
        
        pass


if __name__ == "__main__":
    root = tk.Tk()
    app = POTranslatorGUI(root)
    root.mainloop()
