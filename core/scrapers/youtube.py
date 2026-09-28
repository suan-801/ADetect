"""확인된 채널 ID/handle을 YouTube 공식 API로 조회한다."""
from datetime import datetime, timezone
import requests
from config import settings
from core.jobs import source_cache


@source_cache("youtube")
def fetch_youtube(channel):
    result = {"status": "not_available", "collected_at": datetime.now(timezone.utc).isoformat()}
    if not channel or not settings.YOUTUBE_API_KEY:
        return {**result, "message": "공식 채널 또는 YouTube API 키가 없습니다."}
    if not (channel.startswith("UC") or channel.startswith("@")):
        return {**result, "message": "UC로 시작하는 채널 ID 또는 @handle을 입력하세요."}
    try:
        params = {"key": settings.YOUTUBE_API_KEY, "part": "snippet,statistics,contentDetails",
                  "id" if channel.startswith("UC") else "forHandle": channel}
        response = requests.get("https://www.googleapis.com/youtube/v3/channels", params=params, timeout=15)
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return {**result, "status": "channel_not_found"}
        item = items[0]
        stats = item.get("statistics", {})
        playlist = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        recent = []
        if playlist:
            videos = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params={"key": settings.YOUTUBE_API_KEY,
                "part": "snippet", "playlistId": playlist, "maxResults": 5}, timeout=15)
            videos.raise_for_status()
            recent = [{"title": v["snippet"]["title"], "published_at": v["snippet"].get("publishedAt"),
                       "video_id": v["snippet"].get("resourceId", {}).get("videoId"),
                       "thumbnail_url": next((v["snippet"].get("thumbnails", {}).get(size, {}).get("url")
                                              for size in ("maxres", "standard", "high", "medium", "default")
                                              if v["snippet"].get("thumbnails", {}).get(size, {}).get("url")), None)}
                      for v in videos.json().get("items", [])]
        return {**result, "status": "available", "channel_id": item["id"], "source_url": "https://www.youtube.com/channel/"+item["id"],
                "subscribers": None if stats.get("hiddenSubscriberCount") else stats.get("subscriberCount"),
                "videos": stats.get("videoCount"), "recent_content": recent}
    except (requests.RequestException, ValueError, KeyError):
        return {**result, "message": "YouTube 조회 실패"}
