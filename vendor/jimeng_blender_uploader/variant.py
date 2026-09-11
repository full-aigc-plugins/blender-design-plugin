"""Generated at build time. Do not edit inside packaged zips."""

REGION = 'cn'
PLATFORM = 'mac'
LANGUAGE = 'zh_cn'
TARGET_URL = 'https://jimeng.jianying.com/ai-tool/home'
APP_NAME = '即梦 Seedance 2.5 预览渲染上传器'
SIDEBAR_CATEGORY = 'Jimeng'
TEXT = {
    "browse": "Browse...",
    "camera": "相机",
    "choose_placeholder": "请选择",
    "choose_video_file": "选择视频文件",
    "copy": "复制",
    "default_params": "默认参数",
    "dreamina_link": "链接",
    "error_bridge": "合成失败/{reason}",
    "error_config": "配置获取失败/{reason}",
    "error_existing": "视频处理失败/{reason}",
    "error_file_size": "视频渲染失败/合成失败/视频不能超过{size}",
    "error_frame_range": "帧范围不能超过{count}帧",
    "error_render": "视频渲染失败/{reason}",
    "format": "格式",
    "frame_range": "帧范围",
    "frame_rate": "Frame Rate",
    "generating": "生成中...",
    "link_ready": "链接已生成",
    "max_frames": "最大支持{count}帧",
    "maya_menu_open": "即梦 Seedance 2.5 预览渲染上传器",
    "maya_menu_title": "即梦",
    "min_frames_hint": "最少需要{count}帧（约{seconds}秒）",
    "mode_camera": "相机渲染",
    "mode_camera_display": "相机渲染",
    "mode_local": "本地上传",
    "mode_local_display": "本地上传",
    "open_link": "上传至即梦生成",
    "output_placeholder": "可选：留空则使用默认临时目录",
    "output_to": "保存至",
    "preview": "预览",
    "preview_mode": "预览模式",
    "preview_mode_auto": "auto",
    "render": "渲染",
    "rendering": "渲染中...",
    "resolution": "分辨率",
    "solid": "solid",
    "upload_limit": "最大仅支持上传{size}",
    "video_upload_method": "视频上传方式"
}

def text(key, **kwargs):
    value = TEXT.get(key, key)
    return value.format(**kwargs) if kwargs else value
