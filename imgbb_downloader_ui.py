import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import requests
import time
import os
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import sys


class ImgBBDownloaderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ImgBB 批量下载工具")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1a1a1a')

        # 样式配置
        self.setup_styles()

        # 变量
        self.driver = None
        self.album_data = {}
        self.download_queue = queue.Queue()
        self.is_downloading = False

        # 创建界面
        self.create_widgets()

        # 启动队列监听
        self.check_queue()

    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')

        # 配置样式
        style.configure('Title.TLabel',
                        background='#1a1a1a',
                        foreground='#00ff41',
                        font=('Arial', 16, 'bold'))

        style.configure('Subtitle.TLabel',
                        background='#1a1a1a',
                        foreground='#ffffff',
                        font=('Arial', 10))

        style.configure('Custom.TButton',
                        background='#0066cc',
                        foreground='white',
                        font=('Arial', 10, 'bold'),
                        borderwidth=0)

        style.map('Custom.TButton',
                  background=[('active', '#0080ff')])

        style.configure('Success.TButton',
                        background='#00cc66',
                        foreground='white',
                        font=('Arial', 10, 'bold'))

        style.configure('Warning.TButton',
                        background='#ff6600',
                        foreground='white',
                        font=('Arial', 10, 'bold'))

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        title_label = ttk.Label(main_frame, text="ImgBB 批量下载工具", style='Title.TLabel')
        title_label.pack(pady=(0, 10))

        subtitle_label = ttk.Label(main_frame, text="支持主页批量下载和单个相册下载", style='Subtitle.TLabel')
        subtitle_label.pack(pady=(0, 20))

        # URL输入区域
        url_frame = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        url_frame.pack(fill=tk.X, pady=(0, 20))

        url_title = ttk.Label(url_frame, text="输入链接", style='Subtitle.TLabel')
        url_title.pack(anchor=tk.W, padx=10, pady=(10, 5))

        self.url_entry = tk.Entry(url_frame, font=('Arial', 12), bg='#404040', fg='white',
                                  insertbackground='white', relief=tk.FLAT, bd=5)
        self.url_entry.pack(fill=tk.X, padx=10, pady=(0, 5))

        # 按钮区域
        button_frame = tk.Frame(url_frame, bg='#2d2d2d')
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.analyze_btn = ttk.Button(button_frame, text="分析链接",
                                      command=self.analyze_url, style='Custom.TButton')
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_btn = ttk.Button(button_frame, text="清空",
                                    command=self.clear_url, style='Warning.TButton')
        self.clear_btn.pack(side=tk.LEFT)

        # 相册选择区域
        self.album_frame = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        self.album_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        album_title = ttk.Label(self.album_frame, text="相册列表", style='Subtitle.TLabel')
        album_title.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # 相册列表框架
        list_frame = tk.Frame(self.album_frame, bg='#2d2d2d')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 相册列表
        self.album_listbox = tk.Listbox(list_frame, font=('Arial', 10), bg='#404040',
                                        fg='white', selectbackground='#0066cc',
                                        selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set)
        self.album_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.album_listbox.yview)

        # 相册操作按钮
        album_btn_frame = tk.Frame(self.album_frame, bg='#2d2d2d')
        album_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.select_all_btn = ttk.Button(album_btn_frame, text="全选",
                                         command=self.select_all_albums, style='Custom.TButton')
        self.select_all_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.deselect_all_btn = ttk.Button(album_btn_frame, text="取消全选",
                                           command=self.deselect_all_albums, style='Warning.TButton')
        self.deselect_all_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.download_selected_btn = ttk.Button(album_btn_frame, text="下载选中相册",
                                                command=self.download_selected_albums, style='Success.TButton')
        self.download_selected_btn.pack(side=tk.RIGHT)

        # 进度区域
        progress_frame = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        progress_frame.pack(fill=tk.X, pady=(0, 20))

        progress_title = ttk.Label(progress_frame, text="下载进度", style='Subtitle.TLabel')
        progress_title.pack(anchor=tk.W, padx=10, pady=(10, 5))

        self.progress_var = tk.StringVar(value="等待开始...")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var, style='Subtitle.TLabel')
        self.progress_label.pack(anchor=tk.W, padx=10, pady=(0, 5))

        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 日志区域
        log_frame = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        log_frame.pack(fill=tk.BOTH, expand=True)

        log_title = ttk.Label(log_frame, text="操作日志", style='Subtitle.TLabel')
        log_title.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # 日志文本框
        log_text_frame = tk.Frame(log_frame, bg='#2d2d2d')
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        log_scrollbar = ttk.Scrollbar(log_text_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(log_text_frame, font=('Consolas', 9), bg='#1a1a1a',
                                fg='#00ff41', insertbackground='white',
                                yscrollcommand=log_scrollbar.set, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)

    def log_message(self, message):
        """添加日志消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def clear_url(self):
        """清空URL输入框"""
        self.url_entry.delete(0, tk.END)
        self.album_listbox.delete(0, tk.END)
        self.album_data.clear()

    def analyze_url(self):
        """分析输入的URL"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入URL")
            return

        if not url.startswith('http'):
            messagebox.showerror("错误", "请输入有效的URL")
            return

        # 在新线程中执行分析
        threading.Thread(target=self._analyze_url_thread, args=(url,), daemon=True).start()

    def _analyze_url_thread(self, url):
        """在线程中分析URL"""
        try:
            self.download_queue.put(("status", "正在分析链接..."))
            self.download_queue.put(("progress_start", None))

            # 判断是主页链接还是相册链接
            if '/album/' in url:
                # 单个相册链接
                self.download_queue.put(("log", f"检测到单个相册链接: {url}"))
                self._download_single_album(url)
            else:
                # 主页链接，获取所有相册
                self.download_queue.put(("log", f"检测到主页链接: {url}"))
                self._get_albums_from_homepage(url)

        except Exception as e:
            self.download_queue.put(("error", f"分析链接失败: {str(e)}"))
        finally:
            self.download_queue.put(("progress_stop", None))

    def _get_albums_from_homepage(self, base_url):
        """从主页获取所有相册"""
        try:
            # 设置浏览器
            self.driver = self.setup_driver()
            albums_url = base_url.rstrip('/') + "/albums"

            self.download_queue.put(("log", f"访问相册页面: {albums_url}"))
            self.driver.get(albums_url)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # 滚动加载所有相册
            self.download_queue.put(("log", "正在加载所有相册..."))
            self._load_all_content()

            # 获取相册信息
            albums = self._extract_album_info()

            if albums:
                self.download_queue.put(("albums", albums))
                self.download_queue.put(("log", f"找到 {len(albums)} 个相册"))
            else:
                self.download_queue.put(("error", "未找到任何相册"))

        except Exception as e:
            self.download_queue.put(("error", f"获取相册列表失败: {str(e)}"))
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def _extract_album_info(self):
        """提取相册信息"""
        albums = []
        try:
            # 查找相册链接
            album_links = self.driver.find_elements(By.CSS_SELECTOR, "a.list-item-desc-title-link")

            for link in album_links:
                try:
                    album_name = link.text.strip()
                    album_url = link.get_attribute('href')

                    if album_name and album_url and 'ibb.co/album/' in album_url:
                        albums.append({
                            'name': album_name,
                            'url': album_url
                        })
                        self.download_queue.put(("log", f"找到相册: {album_name} - {album_url}"))
                except Exception as e:
                    continue

        except Exception as e:
            self.download_queue.put(("error", f"提取相册信息失败: {str(e)}"))

        return albums

    def _download_single_album(self, album_url):
        """下载单个相册"""
        try:
            self.driver = self.setup_driver()
            self.download_queue.put(("log", f"开始下载相册: {album_url}"))

            # 获取相册信息
            album_info = self._get_album_info(album_url)
            if album_info:
                # 直接开始下载
                self._process_album_download(album_info['name'], album_info['viewer_links'])
            else:
                self.download_queue.put(("error", "获取相册信息失败"))

        except Exception as e:
            self.download_queue.put(("error", f"下载相册失败: {str(e)}"))
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def _get_album_info(self, album_url):
        """获取单个相册的信息"""
        try:
            self.driver.get(album_url)
            time.sleep(3)

            # 获取相册名称
            album_name = "未知相册"
            title_selectors = ["h1", ".title", ".album-title", ".content-title"]

            for selector in title_selectors:
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    title_text = title_element.text.strip()
                    if title_text and len(title_text) < 100:
                        album_name = title_text
                        break
                except:
                    continue

            if album_name == "未知相册":
                album_id = album_url.split('/')[-1]
                album_name = f"相册_{album_id}"

            # 获取viewer链接
            viewer_links = self._extract_viewer_links_from_album()

            return {
                'name': album_name,
                'url': album_url,
                'viewer_links': viewer_links
            }

        except Exception as e:
            self.download_queue.put(("error", f"获取相册信息失败: {str(e)}"))
            return None

    def _extract_viewer_links_from_album(self):
        """从相册页面提取viewer链接"""
        try:
            # 查找嵌入代码按钮
            embed_selectors = [
                "a[data-tab='tab-embeds']",
                "a#tab-embeds-link",
                "a[href*='/embeds']"
            ]

            embed_button = None
            for selector in embed_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        embed_button = buttons[0]
                        break
                except:
                    continue

            if embed_button:
                self.download_queue.put(("log", "点击嵌入代码按钮..."))
                self.driver.execute_script("arguments[0].click();", embed_button)
                time.sleep(2)

                # 从页面源码提取viewer链接
                page_source = self.driver.page_source
                pattern = r'<a href="(https://ibb\.co/[^/"]+)"[^>]*>'
                matches = re.findall(pattern, page_source)

                # 去重
                viewer_links = list(set(matches))
                self.download_queue.put(("log", f"提取到 {len(viewer_links)} 个viewer链接"))

                return viewer_links
            else:
                self.download_queue.put(("error", "未找到嵌入代码按钮"))
                return []

        except Exception as e:
            self.download_queue.put(("error", f"提取viewer链接失败: {str(e)}"))
            return []

    def select_all_albums(self):
        """全选相册"""
        self.album_listbox.select_set(0, tk.END)

    def deselect_all_albums(self):
        """取消全选相册"""
        self.album_listbox.selection_clear(0, tk.END)

    def download_selected_albums(self):
        """下载选中的相册"""
        selected_indices = self.album_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "请先选择要下载的相册")
            return

        if self.is_downloading:
            messagebox.showwarning("警告", "正在下载中，请稍后...")
            return

        # 在新线程中下载
        threading.Thread(target=self._download_selected_albums_thread,
                         args=(selected_indices,), daemon=True).start()

    def _download_selected_albums_thread(self, selected_indices):
        """在线程中下载选中的相册"""
        try:
            self.is_downloading = True
            self.download_queue.put(("progress_start", None))

            # 设置浏览器
            self.driver = self.setup_driver()

            total_success = 0
            total_failed = 0

            for i, index in enumerate(selected_indices):
                album_info = list(self.album_data.values())[index]
                album_name = album_info['name']
                album_url = album_info['url']

                self.download_queue.put(("status", f"处理相册 {i + 1}/{len(selected_indices)}: {album_name}"))
                self.download_queue.put(("log", f"开始处理相册: {album_name}"))

                # 获取相册详细信息
                detailed_info = self._get_album_info(album_url)
                if detailed_info and detailed_info['viewer_links']:
                    success, failed = self._process_album_download(album_name, detailed_info['viewer_links'])
                    total_success += success
                    total_failed += failed
                else:
                    self.download_queue.put(("log", f"相册 {album_name} 没有找到图片"))

            self.download_queue.put(("status", f"下载完成! 成功: {total_success}, 失败: {total_failed}"))
            self.download_queue.put(("log", f"所有相册下载完成! 总计成功: {total_success}, 失败: {total_failed}"))

        except Exception as e:
            self.download_queue.put(("error", f"下载过程出错: {str(e)}"))
        finally:
            self.is_downloading = False
            self.download_queue.put(("progress_stop", None))
            if self.driver:
                self.driver.quit()
                self.driver = None

    def _process_album_download(self, album_name, viewer_links):
        """处理单个相册的下载"""
        try:
            self.download_queue.put(("log", f"开始获取相册 '{album_name}' 的下载链接..."))

            # 转换为下载链接
            download_links = []
            failed_links = []

            for i, viewer_url in enumerate(viewer_links):
                self.download_queue.put(("status", f"获取下载链接 {i + 1}/{len(viewer_links)}"))
                download_url = self._get_download_link(viewer_url)
                if download_url:
                    download_links.append(download_url)
                else:
                    failed_links.append(viewer_url)

            self.download_queue.put(("log", f"获取到 {len(download_links)} 个下载链接，失败 {len(failed_links)} 个"))

            if download_links:
                # 下载图片
                success, failed = self._download_images(download_links, album_name)
                return success, failed
            else:
                return 0, len(viewer_links)

        except Exception as e:
            self.download_queue.put(("error", f"处理相册下载失败: {str(e)}"))
            return 0, len(viewer_links) if viewer_links else 0

    def _get_download_link(self, viewer_url, retries=3, timeout=10):
        """从viewer链接获取下载链接"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/octet-stream',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://imgbb.com/',
        }

        for attempt in range(retries):
            try:
                response = requests.get(viewer_url, headers=headers, timeout=timeout)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # 查找下载按钮
                    download_link = soup.find('a', {'class': 'btn btn-download default'})

                    if download_link and 'href' in download_link.attrs:
                        return download_link['href']
                    else:
                        # 备用方案
                        pattern = r'https://i\.ibb\.co/[A-Za-z0-9]+/[^"\'\s<>]+'
                        matches = re.findall(pattern, response.text)
                        if matches:
                            return matches[0]

                return None

            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return None

    def _download_images(self, download_links, album_name):
        """下载图片"""
        try:
            # 创建文件夹
            safe_album_name = re.sub(r'[<>:"/\\|?*]', '_', album_name)
            album_dir = os.path.join("downloads", safe_album_name)
            os.makedirs(album_dir, exist_ok=True)

            self.download_queue.put(("log", f"开始下载相册 '{album_name}' 的 {len(download_links)} 张图片..."))

            success_count = 0
            failed_count = 0

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://imgbb.com/',
            }

            for i, url in enumerate(download_links):
                try:
                    self.download_queue.put(("status", f"下载图片 {i + 1}/{len(download_links)}"))

                    filename = url.split('/')[-1]
                    if not filename or '.' not in filename:
                        filename = f"image_{i + 1}.jpg"

                    file_path = os.path.join(album_dir, filename)

                    # 检查文件是否已存在
                    if os.path.exists(file_path):
                        success_count += 1
                        continue

                    response = requests.get(url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                        success_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    failed_count += 1

                time.sleep(0.5)  # 控制下载速度

            self.download_queue.put(
                ("log", f"相册 '{album_name}' 下载完成! 成功: {success_count}, 失败: {failed_count}"))
            return success_count, failed_count

        except Exception as e:
            self.download_queue.put(("error", f"下载图片失败: {str(e)}"))
            return 0, len(download_links)

    def setup_driver(self):
        """设置Chrome浏览器"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # 无头模式
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _load_all_content(self):
        """滚动加载所有内容"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_change_count = 0

        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            try:
                load_more_buttons = self.driver.find_elements(By.XPATH,
                                                              "//button[contains(text(), 'Load more')] | //a[contains(text(), 'Load more')] | //*[contains(@class, 'load-more')]")

                clicked = False
                for btn in load_more_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        try:
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.download_queue.put(("log", "点击了Load more按钮"))
                            time.sleep(3)
                            clicked = True
                            break
                        except:
                            continue

                if clicked:
                    no_change_count = 0
            except:
                pass

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_change_count += 1
                if no_change_count >= 3:
                    break
            else:
                no_change_count = 0

            last_height = new_height

    def check_queue(self):
        """检查队列中的消息"""
        try:
            while True:
                message_type, data = self.download_queue.get_nowait()

                if message_type == "log":
                    self.log_message(data)
                elif message_type == "error":
                    self.log_message(f"错误: {data}")
                    messagebox.showerror("错误", data)
                elif message_type == "status":
                    self.progress_var.set(data)
                elif message_type == "progress_start":
                    self.progress_bar.start()
                elif message_type == "progress_stop":
                    self.progress_bar.stop()
                elif message_type == "albums":
                    self._update_album_list(data)

        except queue.Empty:
            pass

        # 继续检查队列
        self.root.after(100, self.check_queue)

    def _update_album_list(self, albums):
        """更新相册列表"""
        self.album_listbox.delete(0, tk.END)
        self.album_data.clear()

        for i, album in enumerate(albums):
            self.album_listbox.insert(tk.END, f"{album['name']} ({album['url']})")
            self.album_data[i] = album


def main():
    """主函数"""
    root = tk.Tk()
    app = ImgBBDownloaderUI(root)

    # 设置窗口图标和其他属性
    try:
        root.iconbitmap('icon.ico')  # 如果有图标文件
    except:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()