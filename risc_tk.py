import tkinter as tk
from tkinter import filedialog, messagebox
import tempfile, subprocess, sys, os, threading

class RiscVUI:
    def __init__(self, root):
        self.root = root
        root.title("RISC-V Simulator - UI")
        root.geometry("1000x700")

        # Top frame: code editor
        top = tk.Frame(root)
        top.pack(fill='both', expand=True)

        editor_label = tk.Label(top, text="Assembly code (.s):")
        editor_label.pack(anchor='w')

        self.editor = tk.Text(top, wrap='none', undo=True, height=20)
        self.editor.pack(fill='both', expand=True, padx=6, pady=4)

        # Buttons
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill='x', padx=6, pady=4)

        self.load_btn = tk.Button(btn_frame, text="Load .s file", command=self.load_file)
        self.load_btn.pack(side='left')
        self.save_btn = tk.Button(btn_frame, text="Save .s file", command=self.save_file)
        self.save_btn.pack(side='left')
        self.run_btn = tk.Button(btn_frame, text="Run (execute)", command=self.run_sim)
        self.run_btn.pack(side='left')
        self.clear_btn = tk.Button(btn_frame, text="Clear Output", command=self.clear_output)
        self.clear_btn.pack(side='left')
        self.reset_btn = tk.Button(btn_frame, text="Reset Editor", command=self.reset_editor)
        self.reset_btn.pack(side='left')

        # Bottom: output / trace
        out_label = tk.Label(root, text="Simulator output (stdout / stderr):")
        out_label.pack(anchor='w', padx=6)

        self.output = tk.Text(root, wrap='none', height=12, bg='#111', fg='#ddd')
        self.output.pack(fill='both', expand=False, padx=6, pady=4)

        # status bar
        self.status = tk.Label(root, text="Ready", anchor='w')
        self.status.pack(fill='x', padx=6, pady=(0,6))

        # preload a small example
        self.load_example()
        self._running = False

    def load_example(self):
        example = """start:
    addi x1, x0, 10      # x1 = 10
    addi x2, x0, 20      # x2 = 20
    add  x3, x1, x2      # x3 = x1 + x2
    sw   x3, 0(x0)       # store x3 at mem[0]
    halt
"""
        self.editor.delete('1.0', tk.END)
        self.editor.insert('1.0', example)

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Assembly files","*.s"),("All files","*.*")])
        if not path:
            return
        with open(path, 'r') as f:
            txt = f.read()
        self.editor.delete('1.0', tk.END)
        self.editor.insert('1.0', txt)
        self.status['text'] = f"Loaded {os.path.basename(path)}"

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".s", filetypes=[("Assembly files","*.s"),("All files","*.*")])
        if not path:
            return
        with open(path, 'w') as f:
            f.write(self.editor.get('1.0', tk.END))
        self.status['text'] = f"Saved {os.path.basename(path)}"

    def clear_output(self):
        self.output.delete('1.0', tk.END)
        self.status['text'] = "Output cleared"

    def reset_editor(self):
        if messagebox.askyesno("Reset", "Clear editor and load example?"):
            self.load_example()
            self.status['text'] = "Editor reset"

    def run_sim(self):
        if self._running:
            messagebox.showinfo("Running", "Simulator already running")
            return

        asm = self.editor.get('1.0', tk.END).strip()
        if not asm:
            messagebox.showwarning("No code", "Editor is empty.")
            return

        # write to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.s', mode='w', encoding='utf-8')
        tmp.write(asm)
        tmp.flush()
        tmp.close()
        tmp_path = tmp.name

        sim_script = os.path.join(os.getcwd(), "riscv_sim.py")
        if not os.path.exists(sim_script):
            messagebox.showerror("Missing file", f"Cannot find riscv_sim.py in {os.getcwd()}")
            os.unlink(tmp_path)
            return

        self._running = True
        self._set_buttons_state('disabled')
        self.status['text'] = "Running simulator..."
        self.output.insert(tk.END, f"> Running riscv_sim.py on {tmp_path}\n")
        self.output.see(tk.END)
        self.root.update()

        def target():
            try:
                proc = subprocess.run([sys.executable, sim_script, tmp_path], capture_output=True, text=True, check=False, timeout=10)
                out = proc.stdout
                err = proc.stderr
                if out:
                    self.output.insert(tk.END, out + "\n")
                if err:
                    self.output.insert(tk.END, "=== STDERR ===\n" + err + "\n")
                self.status['text'] = f"Finished. Return code: {proc.returncode}"
            except subprocess.TimeoutExpired:
                self.output.insert(tk.END, "ERROR: Simulator timed out (10s)\n")
                self.status['text'] = "Timed out"
            except Exception as e:
                self.output.insert(tk.END, f"ERROR: {e}\n")
                self.status['text'] = "Error"
            finally:
                self.output.see(tk.END)
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                self._running = False
                self._set_buttons_state('normal')

        t = threading.Thread(target=target, daemon=True)
        t.start()

    def _set_buttons_state(self, state):
        for w in (self.load_btn, self.save_btn, self.run_btn, self.clear_btn, self.reset_btn):
            w['state'] = state

if __name__ == "__main__":
    root = tk.Tk()
    app = RiscVUI(root)
    root.mainloop()