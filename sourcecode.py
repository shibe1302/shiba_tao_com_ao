

import ctypes

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
import json


# ─────────────────────────────────────────────────────────────────
#  Hằng số - Đường dẫn tìm setupc.exe
# ─────────────────────────────────────────────────────────────────

# COM0COM_PATHS: list[str] = [
#     r"C:\Program Files (x86)\com0com\setupc.exe",
#     r"C:\Program Files (x86)\com0com\setupc.exe",
#     r"C:\com0com\setupc.exe",
# ]
# --- Cấu hình mặc định ---
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "com0com_paths": [
        r"C:\Program Files (x86)\com0com\setupc.exe",
        r"C:\Program Files\com0com\setupc.exe",
        r"C:\com0com\setupc.exe"
    ],
    "app_settings": {
        "theme": "dark",
        "default_com_a": "COM8",
        "default_com_b": "COM9"
    }
}

def load_config() -> dict:
    """Đọc config từ JSON. Nếu không có, tự tạo mới từ DEFAULT_CONFIG."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                # Merge dữ liệu để đảm bảo không thiếu key nếu người dùng sửa file lỗi
                full_config = DEFAULT_CONFIG.copy()
                if isinstance(user_data, dict):
                    full_config.update(user_data)
                return full_config
        except Exception:
            return DEFAULT_CONFIG
    else:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
        return DEFAULT_CONFIG

# Khởi tạo cấu hình ngay từ đầu
APP_CONFIG = load_config()
# Ép kiểu rõ ràng để trình kiểm lỗi không báo Type Unknown/None
COM0COM_PATHS: list[str] = list(APP_CONFIG.get("com0com_paths", DEFAULT_CONFIG["com0com_paths"]))
APP_VERSION = "1.1"
COM0COM_DOWNLOAD = "https://sourceforge.net/projects/com0com/files/com0com/"


# ─────────────────────────────────────────────────────────────────
#  Tiện ích hệ thống
# ─────────────────────────────────────────────────────────────────

def is_admin() -> bool:
    """Kiểm tra xem tiến trình hiện tại có đang chạy với quyền Admin không."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def find_setupc() -> str | None:
    """
    Tìm đường dẫn tới setupc.exe của com0com.
    Trả về đường dẫn đầy đủ nếu tìm thấy, None nếu không tìm thấy.
    """
    # Kiểm tra các đường dẫn cố định trước
    for path in COM0COM_PATHS:
        if os.path.isfile(path):
            return path

    # Thử tìm qua biến môi trường PATH
    try:
        result = subprocess.run(
            ["where", "setupc.exe"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            first_line = result.stdout.strip().splitlines()[0]
            if first_line:
                return first_line
    except Exception:
        pass

    return None


def run_setupc(args: list[str], setupc_path: str | None) -> tuple[bool, str]:
    if not setupc_path:
        return False, "Không tìm thấy setupc.exe — hãy kiểm tra com0com đã cài chưa."

    try:
        # Lấy đường dẫn thư mục chứa setupc.exe
        work_dir = os.path.dirname(os.path.abspath(setupc_path))
        
        cmd = [setupc_path] + args
        result = subprocess.run(
            cmd,
            cwd=work_dir,  # QUAN TRỌNG: Thiết lập thư mục làm việc tại đây
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output

    except Exception as exc:
        return False, str(exc)
    """
    Chạy lệnh setupc.exe với các tham số chỉ định.

    Args:
        args:         Danh sách tham số truyền vào setupc.exe
        setupc_path:  Đường dẫn tới setupc.exe (có thể là None)

    Returns:
        Tuple (success: bool, output: str)
    """
    if not setupc_path:
        return False, "Không tìm thấy setupc.exe — hãy kiểm tra com0com đã cài chưa."

    try:
        cmd = [setupc_path] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output

    except FileNotFoundError:
        return False, f"Không tìm thấy file: {setupc_path}"
    except subprocess.TimeoutExpired:
        return False, "Lệnh chạy quá 15 giây, có thể bị treo."
    except PermissionError:
        return False, "Từ chối truy cập. Hãy chạy phần mềm với quyền Administrator."
    except Exception as exc:
        return False, str(exc)


def parse_pairs(output: str) -> list[dict]:
    """
    Phân tích output mới của com0com.
    Định dạng:
       CNCA2 PortName=COM8
       CNCB2 PortName=COM9
    """
    pairs: list[dict] = []
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    
    # Duyệt qua danh sách, mỗi lần lấy 2 dòng (A và B)
    for i in range(0, len(lines) - 1, 2):
        line_a = lines[i]
        line_b = lines[i+1]
        
        # Regex để bắt tên Device và PortName
        # Ví dụ: CNCA2 PortName=COM8
        pattern = re.compile(r"(\S+)\s+PortName=(\S+)", re.IGNORECASE)
        
        match_a = pattern.search(line_a)
        match_b = pattern.search(line_b)
        
        if match_a and match_b:
            dev_a, com_a = match_a.groups()
            dev_b, com_b = match_b.groups()
            
            # Lấy index từ tên thiết bị (ví dụ CNCA2 -> index là 2)
            idx_match = re.search(r"\d+", dev_a)
            index = idx_match.group() if idx_match else str(i // 2)
            
            # Bỏ qua các port chưa được cấu hình (PortName=- hoặc COM#)
            if com_a in ("-", "COM#") or com_b in ("-", "COM#"):
                continue

            pairs.append({
                "index": index,
                "devA": dev_a,
                "comA": com_a,
                "devB": dev_b,
                "comB": com_b,
            })
            
    return pairs
# ─────────────────────────────────────────────────────────────────
#  Bảng màu & Theme
# ─────────────────────────────────────────────────────────────────

DARK_BG     = "#0f1117"
PANEL_BG    = "#1a1d27"
CARD_BG     = "#22263a"
ACCENT      = "#00d4ff"
ACCENT2     = "#7c3aed"
SUCCESS     = "#22c55e"
DANGER      = "#ef4444"
WARNING     = "#f59e0b"
TEXT_MAIN   = "#e2e8f0"
TEXT_DIM    = "#64748b"
BORDER      = "#2d3154"


# ─────────────────────────────────────────────────────────────────
#  Giao diện chính
# ─────────────────────────────────────────────────────────────────

class VCOMApp(tk.Tk):
    """Cửa sổ chính của ứng dụng Virtual COM Port Manager."""

    def __init__(self) -> None:
        super().__init__()

        self.title(f"Virtual COM Port Manager  v{APP_VERSION}")
        self.geometry("820x600")
        self.minsize(700, 520)
        self.configure(bg=DARK_BG)
        self.resizable(True, True)

        # Trạng thái nội bộ
        self.setupc_path: str | None = find_setupc()
        self.pairs: list[dict] = []

        self._build_ui()

        # Khởi động: tải danh sách hoặc hiển thị cảnh báo
        if self.setupc_path:
            self._refresh_pairs()
        else:
            self._show_install_notice()

    # ──────────────────────────── Xây dựng UI ───────────────────────

    def _build_ui(self) -> None:
        self._build_header()
        self._build_divider()
        self._build_log_panel()
        self._build_add_panel()
        self._build_main_area()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=PANEL_BG, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=PANEL_BG)
        left.pack(side="left", padx=20, pady=0)

        tk.Label(
            left, text="⚡",
            font=("Segoe UI Emoji", 22), bg=PANEL_BG, fg=ACCENT,
        ).pack(side="left")

        tk.Label(
            left, text="  Virtual COM Port Manager",
            font=("Consolas", 15, "bold"), bg=PANEL_BG, fg=TEXT_MAIN,
        ).pack(side="left")

        tk.Label(
            left, text=f"  v{APP_VERSION}  |  Powered by com0com",
            font=("Consolas", 9), bg=PANEL_BG, fg=TEXT_DIM,
        ).pack(side="left", pady=(7, 0))

        self.driver_badge = tk.Label(
            header,
            text="● Đang kiểm tra...",
            font=("Consolas", 9, "bold"),
            bg=PANEL_BG, fg=WARNING,
            padx=14, pady=5,
        )
        self.driver_badge.pack(side="right", padx=18)

    def _build_divider(self) -> None:
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _build_main_area(self) -> None:
        """Khung hiển thị danh sách COM pair."""
        frame = tk.Frame(self, bg=DARK_BG)
        frame.pack(side="top", fill="both", expand=True, padx=16, pady=(12, 0))

        # 1. Tiêu đề + nút Làm mới (Phía trên)
        row = tk.Frame(frame, bg=DARK_BG)
        row.pack(fill="x", pady=(0, 6))

        tk.Label(
            row, text="DANH SÁCH COM PAIR",
            font=("Consolas", 10, "bold"), bg=DARK_BG, fg=ACCENT,
        ).pack(side="left")

        self.btn_refresh = self._make_button(
            row, "↻  Làm mới", self._on_refresh,
            bg=CARD_BG, fg=TEXT_MAIN, pad=(10, 4),
        )
        self.btn_refresh.pack(side="right")

        # 2. Nút xóa (Phía dưới cùng của khu vực này)
        # Pack side="bottom" trước để nó luôn giữ chỗ ở dưới bảng
        btn_row = tk.Frame(frame, bg=DARK_BG)
        btn_row.pack(side="bottom", fill="x", pady=8)

        self.btn_delete = self._make_button(
            btn_row, "🗑  Xóa Pair đã chọn", self._on_delete,
            bg=DANGER, fg="white", pad=(16, 6),
        )
        self.btn_delete.pack(side="right")

        # 3. TreeView (Khu vực giữa - chiếm không gian còn lại)
        tree_frame = tk.Frame(frame, bg=CARD_BG)
        tree_frame.pack(side="top", fill="both", expand=True)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "VCOM.Treeview",
            background=CARD_BG, foreground=TEXT_MAIN,
            fieldbackground=CARD_BG, rowheight=38,
            font=("Consolas", 10), borderwidth=0,
        )
        style.configure(
            "VCOM.Treeview.Heading",
            background=PANEL_BG, foreground=ACCENT,
            font=("Consolas", 9, "bold"), relief="flat",
        )
        style.map("VCOM.Treeview", background=[("selected", ACCENT2)])

        cols = ("index", "com_a", "com_b", "device_a", "device_b")
        self.tree = ttk.Treeview(
            tree_frame, columns=cols,
            show="headings", style="VCOM.Treeview", 
            selectmode="browse",
            height=6  # Giới hạn chiều cao để đảm bảo nút xóa luôn thấy được
        )
        
        self.tree.heading("index",    text="#")
        self.tree.heading("com_a",    text="COM A  →")
        self.tree.heading("com_b",    text="→  COM B")
        self.tree.heading("device_a", text="Device A")
        self.tree.heading("device_b", text="Device B")

        self.tree.column("index",    width=40,  anchor="center")
        self.tree.column("com_a",    width=150, anchor="center")
        self.tree.column("com_b",    width=150, anchor="center")
        self.tree.column("device_a", width=130, anchor="center")
        self.tree.column("device_b", width=130, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
    def _build_add_panel(self) -> None:
        """Panel nhập để thêm COM pair mới."""
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="top")

        panel = tk.Frame(self, bg=PANEL_BG)
        panel.pack(fill="x")
        tk.Frame(panel, bg=BORDER, height=1).pack(fill="x", side="top")

        inner = tk.Frame(panel, bg=PANEL_BG)
        inner.pack(padx=16, pady=10)

        inner = tk.Frame(panel, bg=PANEL_BG)
        inner.pack(padx=16, pady=10)

        tk.Label(
            inner, text="THÊM COM PAIR MỚI",
            font=("Consolas", 9, "bold"), bg=PANEL_BG, fg=ACCENT,
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        # COM A
        tk.Label(
            inner, text="COM A:", font=("Consolas", 10),
            bg=PANEL_BG, fg=TEXT_MAIN,
        ).grid(row=1, column=0, padx=(0, 6))

        self.var_com_a = tk.StringVar(value="COM8")
        self._make_entry(inner, self.var_com_a, width=8).grid(row=1, column=1, padx=(0, 12))

        tk.Label(
            inner, text="⟺",
            font=("Segoe UI Emoji", 16), bg=PANEL_BG, fg=ACCENT,
        ).grid(row=1, column=2, padx=8)

        # COM B
        tk.Label(
            inner, text="COM B:", font=("Consolas", 10),
            bg=PANEL_BG, fg=TEXT_MAIN,
        ).grid(row=1, column=3, padx=(12, 6))

        self.var_com_b = tk.StringVar(value="COM9")
        self._make_entry(inner, self.var_com_b, width=8).grid(row=1, column=4, padx=(0, 12))

        self.btn_add = self._make_button(
            inner, "＋  Thêm Pair", self._on_add,
            bg=SUCCESS, fg=DARK_BG, pad=(18, 7),
        )
        self.btn_add.grid(row=1, column=5, padx=(8, 0))

        tk.Label(
            inner,
            text="💡 Ví dụ: COM8 ⟺ COM9  —  Nối phần mềm A vào COM8, phần mềm B vào COM9",
            font=("Consolas", 8), bg=PANEL_BG, fg=TEXT_DIM,
        ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))

    def _build_log_panel(self) -> None:
        """Thanh log nhỏ ở cuối cửa sổ."""
        log_frame = tk.Frame(self, bg=DARK_BG)
        log_frame.pack(side="bottom", fill="x", padx=16, pady=6)

        log_frame = tk.Frame(self, bg=DARK_BG)
        log_frame.pack(fill="x", padx=16, pady=6)

        tk.Label(
            log_frame, text="LOG",
            font=("Consolas", 8, "bold"), bg=DARK_BG, fg=TEXT_DIM,
        ).pack(anchor="w")

        self.log_text = tk.Text(
            log_frame, height=4,
            bg=DARK_BG, fg=TEXT_DIM,
            font=("Consolas", 8), relief="flat",
            state="disabled", insertbackground=ACCENT,
            wrap="word", bd=0,
        )
        self.log_text.pack(fill="x")

    # ──────────────────────────── Widget Helpers ─────────────────────

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        bg: str,
        fg: str,
        pad: tuple[int, int] = (12, 5),
    ) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg,
            activebackground=self._lighten(bg), activeforeground=fg,
            font=("Consolas", 9, "bold"), relief="flat",
            cursor="hand2", padx=pad[0], pady=pad[1], bd=0,
        )
        btn.bind("<Enter>", lambda _e: btn.configure(bg=self._lighten(bg)))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg))
        return btn

    def _make_entry(self, parent: tk.Widget, var: tk.StringVar, width: int = 10) -> tk.Entry:
        return tk.Entry(
            parent, textvariable=var, width=width,
            bg=CARD_BG, fg=TEXT_MAIN, insertbackground=ACCENT,
            font=("Consolas", 11, "bold"), relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )

    @staticmethod
    def _lighten(hex_color: str) -> str:
        """Làm sáng màu hex thêm một chút cho hiệu ứng hover."""
        try:
            r = min(255, int(hex_color[1:3], 16) + 20)
            g = min(255, int(hex_color[3:5], 16) + 20)
            b = min(255, int(hex_color[5:7], 16) + 20)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    # ──────────────────────────── Hành động UI ───────────────────────

    def _log(self, msg: str) -> None:
        """Thêm một dòng vào log panel."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"› {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_badge(self, ok: bool) -> None:
        if ok:
            self.driver_badge.configure(text="● Driver: OK", fg=SUCCESS)
        else:
            self.driver_badge.configure(text="● Driver: Chưa cài", fg=DANGER)

    def _show_install_notice(self) -> None:
        """Hiển thị thông báo và hướng dẫn cài com0com."""
        self._set_badge(False)
        self._log("Không tìm thấy com0com!")
        self._log(f"Tải về: {COM0COM_DOWNLOAD}")
        self._log("Sau khi cài xong, khởi động lại phần mềm.")

        if messagebox.askyesno(
            "Cần cài com0com",
            "⚠️  Không tìm thấy com0com driver!\n\n"
            "com0com là driver mã nguồn mở (miễn phí) để tạo\n"
            "Virtual COM Port trên Windows.\n\n"
            "Bước cài đặt:\n"
            "  1. Tải com0com tại Sourceforge\n"
            "  2. Chạy installer với quyền Administrator\n"
            "  3. Khởi động lại phần mềm này\n\n"
            "Mở trang tải về ngay bây giờ?",
            icon="warning",
        ):
            webbrowser.open(COM0COM_DOWNLOAD)

    # ──────────────── Refresh danh sách ─────────────────────────────

    def _refresh_pairs(self) -> None:
        if not self.setupc_path:
            return
        self._log("Đang tải danh sách COM pair...")

        def _worker() -> None:
            ok, out = run_setupc(["list"], self.setupc_path)
            self.after(0, lambda: self._update_tree(ok, out))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_tree(self, ok: bool, output: str) -> None:
        print(f"DEBUG - Raw Output:\n{output}")
        if not ok:
            self._set_badge(False)
            self._log(f"Lỗi khi tải danh sách: {output}")
            return

        self._set_badge(True)
        self.pairs = parse_pairs(output)
        self.tree.delete(*self.tree.get_children())

        for pair in self.pairs:
            self.tree.insert(
                "", "end",
                values=(pair["index"], pair["comA"], pair["comB"], pair["devA"], pair["devB"]),
            )

        count = len(self.pairs)
        self._log(f"Tìm thấy {count} pair{'s' if count != 1 else ''}.")

    def _on_refresh(self) -> None:
        if not self.setupc_path:
            self._show_install_notice()
            return
        self._refresh_pairs()

    # ──────────────── Thêm pair ──────────────────────────────────────

    def _on_add(self) -> None:
        if not self.setupc_path:
            self._show_install_notice()
            return

        com_a = self.var_com_a.get().strip().upper()
        com_b = self.var_com_b.get().strip().upper()

        # Tự động thêm tiền tố "COM" nếu chỉ nhập số
        if com_a.isdigit():
            com_a = "COM" + com_a
        if com_b.isdigit():
            com_b = "COM" + com_b

        if not com_a or not com_b:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập tên cả hai COM port.")
            return

        if not com_a.startswith("COM") or not com_b.startswith("COM"):
            messagebox.showwarning(
                "Sai định dạng",
                "Tên COM port phải có dạng COMx (ví dụ: COM8, COM9).",
            )
            return

        if com_a == com_b:
            messagebox.showwarning("Lỗi", "COM A và COM B không được trùng nhau.")
            return

        self._log(f"Đang tạo pair {com_a} ⟺ {com_b}...")
        self.btn_add.configure(state="disabled", text="Đang thêm...")

        def _worker() -> None:
            ok, out = run_setupc(
                ["install", f"PortName={com_a}", f"PortName={com_b}"],
                self.setupc_path,
            )
            self.after(0, lambda: self._on_add_done(ok, out, com_a, com_b))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_add_done(self, ok: bool, output: str, com_a: str, com_b: str) -> None:
        self.btn_add.configure(state="normal", text="＋  Thêm Pair")
        if ok:
            self._log(f"✓ Đã tạo pair {com_a} ⟺ {com_b}.")
            # Gợi ý tên COM tiếp theo
            try:
                num = int(re.search(r"\d+", com_b).group())  # type: ignore[union-attr]
                self.var_com_a.set(f"COM{num + 2}")
                self.var_com_b.set(f"COM{num + 3}")
            except Exception:
                pass
            self._refresh_pairs()
        else:
            self._log(f"✗ Lỗi tạo pair: {output}")
            messagebox.showerror(
                "Lỗi",
                f"Không thể tạo pair {com_a} ⟺ {com_b}.\n\n"
                f"Chi tiết: {output}\n\n"
                "💡 Hãy chắc chắn đang chạy với quyền Administrator.",
            )

    # ──────────────── Xóa pair ───────────────────────────────────────

    def _on_delete(self) -> None:
        if not self.setupc_path:
            self._show_install_notice()
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một pair trong danh sách để xóa.")
            return

        values = self.tree.item(selected[0])["values"]
        idx, com_a, com_b = str(values[0]), str(values[1]), str(values[2])

        if not messagebox.askyesno(
            "Xác nhận xóa",
            f"Xóa pair #{idx}?\n\n  {com_a}  ⟺  {com_b}\n\nThao tác không thể hoàn tác.",
            icon="warning",
        ):
            return

        self._log(f"Đang xóa pair #{idx} ({com_a} ⟺ {com_b})...")
        self.btn_delete.configure(state="disabled", text="Đang xóa...")

        def _worker() -> None:
            ok, out = run_setupc(["remove", idx], self.setupc_path)
            self.after(0, lambda: self._on_delete_done(ok, out, idx, com_a, com_b))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_delete_done(
        self, ok: bool, output: str, idx: str, com_a: str, com_b: str
    ) -> None:
        self.btn_delete.configure(state="normal", text="🗑  Xóa Pair đã chọn")
        if ok:
            self._log(f"✓ Đã xóa pair #{idx} ({com_a} ⟺ {com_b}).")
            self._refresh_pairs()
        else:
            self._log(f"✗ Lỗi xóa pair: {output}")
            messagebox.showerror(
                "Lỗi",
                f"Không thể xóa pair #{idx}.\n\n"
                f"Chi tiết: {output}\n\n"
                "💡 Hãy chắc chắn đang chạy với quyền Administrator.",
            )


# ─────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    if sys.platform == "win32" and not is_admin():
        # Tự nâng quyền Admin bằng UAC
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
        )
        return

    app = VCOMApp()
    app.mainloop()


if __name__ == "__main__":
    main()