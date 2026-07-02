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
        self.root.title("凯普勒 186F PO 翻译工具 v1.3")
        self.root.geometry("760x620")
        self.root.resizable(True, True)

        self.input_po_path = tk.StringVar()
        self.translations_json_path = tk.StringVar()
        self.output_po_path = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        title_label = tk.Label(self.root, text="凯普勒 186F PO 文件批量翻译工具", 
                               font=("Microsoft YaHei", 16, "bold"), pady=10)
        title_label.pack()

        desc_label = tk.Label(self.root, text="支持提取 → AI翻译 → 应用 一条龙操作", 
                              font=("Microsoft YaHei", 10), fg="gray")
        desc_label.pack(pady=(0, 10))

        frame_files = ttk.LabelFrame(self.root, text="文件选择", padding=10)
        frame_files.pack(fill="x", padx=15, pady=5)

        tk.Label(frame_files, text="原始 PO 文件：").grid(row=0, column=0, sticky="w", pady=4)
        tk.Entry(frame_files, textvariable=self.input_po_path, width=60).grid(row=0, column=1, padx=5)
        tk.Button(frame_files, text="浏览", command=self.select_input_po).grid(row=0, column=2)

        tk.Label(frame_files, text="翻译结果 JSON：").grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(frame_files, textvariable=self.translations_json_path, width=60).grid(row=1, column=1, padx=5)
        tk.Button(frame_files, text="浏览", command=self.select_translations_json).grid(row=1, column=2)

        tk.Label(frame_files, text="输出中文 PO 文件：").grid(row=2, column=0, sticky="w", pady=4)
        tk.Entry(frame_files, textvariable=self.output_po_path, width=60).grid(row=2, column=1, padx=5)
        tk.Button(frame_files, text="保存位置", command=self.select_output_po).grid(row=2, column=2)

        frame_buttons = ttk.Frame(self.root)
        frame_buttons.pack(fill="x", padx=15, pady=12)

        btn_style = {"width": 20, "height": 2, "font": ("Microsoft YaHei", 10)}

        tk.Button(frame_buttons, text="① 提取未翻译内容", 
                  command=self.extract_untranslated, bg="#4CAF50", fg="white", **btn_style).pack(side="left", padx=6)
        tk.Button(frame_buttons, text="② 应用翻译", 
                  command=self.apply_translations_threaded, bg="#2196F3", fg="white", **btn_style).pack(side="left", padx=6)
        tk.Button(frame_buttons, text="查看进度", 
                  command=self.show_stats, bg="#FF9800", fg="white", **btn_style).pack(side="left", padx=6)

        frame_log = ttk.LabelFrame(self.root, text="执行日志", padding=8)
        frame_log.pack(fill="both", expand=True, padx=15, pady=5)

        self.progress = ttk.Progressbar(frame_log, length=700, mode="determinate")
        self.progress.pack(pady=5)

        self.log_text = tk.Text(frame_log, height=16, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        self.status_label = tk.Label(self.root, text="就绪", bd=1, relief="sunken", anchor="w")
        self.status_label.pack(fill="x", side="bottom")

    def log(self, message):
        self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def select_input_po(self):
        path = filedialog.askopenfilename(title="选择原始 PO 文件", filetypes=[("PO files", "*.po")])
        if path:
            self.input_po_path.set(path)
            if not self.output_po_path.get():
                p = Path(path)
                self.output_po_path.set(str(p.parent / f"{p.stem}.zh_CN.po"))

    def select_translations_json(self):
        path = filedialog.askopenfilename(title="选择翻译 JSON", filetypes=[("JSON files", "*.json")])
        if path:
            self.translations_json_path.set(path)

    def select_output_po(self):
        path = filedialog.asksaveasfilename(title="保存最终 PO", defaultextension=".po", filetypes=[("PO files", "*.po")])
        if path:
            self.output_po_path.set(path)

    def extract_untranslated(self):
        if not self.input_po_path.get():
            messagebox.showwarning("提示", "请先选择原始 PO 文件")
            return

        output_json = filedialog.asksaveasfilename(
            title="保存未翻译内容 JSON",
            defaultextension=".json",
            initialfile="untranslated.json",
            filetypes=[("JSON files", "*.json")]
        )
        if not output_json:
            return

        try:
            self.log("开始提取未翻译内容...")
            entries, _ = self.parse_po_file(self.input_po_path.get())
            untranslated = []

            for idx, entry in enumerate(entries, 1):
                if entry.get("needs_translation") and entry.get("msgid", "").strip():
                    untranslated.append({
                        "id": idx,
                        "msgid": entry["msgid"],
                        "msgstr": ""
                    })

            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(untranslated, f, ensure_ascii=False, indent=2)

            self.log(f"✅ 提取完成！共 {len(untranslated)} 条未翻译内容")
            self.log(f"已保存到：{output_json}")
            messagebox.showinfo("完成", f"成功提取 {len(untranslated)} 条未翻译内容！\n请将该 JSON 文件分批喂给 AI 翻译。")

        except Exception as e:
            self.log(f"❌ 提取失败：{str(e)}")
            messagebox.showerror("错误", str(e))

    def apply_translations_threaded(self):
        thread = threading.Thread(target=self.apply_translations)
        thread.daemon = True
        thread.start()

    def apply_translations(self):
        input_po = self.input_po_path.get()
        trans_json = self.translations_json_path.get()
        output_po = self.output_po_path.get()

        if not all([input_po, trans_json, output_po]):
            messagebox.showwarning("提示", "请填写所有文件路径")
            return

        try:
            self.log("开始应用翻译...")
            entries, content = self.parse_po_file(input_po)

            with open(trans_json, "r", encoding="utf-8") as f:
                translations = json.load(f)

            trans_dict = {}
            if isinstance(translations, list):
                for item in translations:
                    if item.get("msgstr"):
                        trans_dict[item["msgid"]] = item["msgstr"]

            new_content = content
            translated_count = 0

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

                if i % 100 == 0:
                    self.progress["value"] = int((i + 1) / len(entries) * 100)

            new_content = self.update_po_header(new_content)

            with open(output_po, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.progress["value"] = 100
            self.log(f"✅ 完成！共应用 {translated_count} 条翻译")
            messagebox.showinfo("完成", f"成功应用 {translated_count} 条翻译！\n文件已保存。")

        except Exception as e:
            self.log(f"❌ 失败: {e}")
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
        if not self.input_po_path.get():
            messagebox.showwarning("提示", "请先选择 PO 文件")
            return
        try:
            entries, _ = self.parse_po_file(self.input_po_path.get())
            total = len(entries)
            translated = sum(1 for e in entries if e["msgstr"] and e["msgstr"] != e["msgid"])
            percent = (translated / total * 100) if total > 0 else 0
            msg = f"总条目：{total}\n已翻译：{translated}\n待翻译：{total - translated}\n完成度：{percent:.1f}%"
            messagebox.showinfo("翻译进度", msg)
            self.log(f"当前进度：{percent:.1f}% ({translated}/{total})")
        except Exception as e:
            messagebox.showerror("错误", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = POTranslatorGUI(root)
    root.mainloop()
