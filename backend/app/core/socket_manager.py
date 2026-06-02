from typing import List, Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # User-specific connections for messaging
        self.user_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def connect_user(self, user_id: str, websocket: WebSocket):
        """Connect a user-specific WebSocket for messaging"""
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
        print(f"[WebSocket] User {user_id} connected. Total connections: {len(self.user_connections[user_id])}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    def disconnect_user(self, user_id: str, websocket: WebSocket):
        """Disconnect a user-specific WebSocket"""
        if user_id in self.user_connections and websocket in self.user_connections[user_id]:
            self.user_connections[user_id].remove(websocket)
            print(f"[WebSocket] User {user_id} disconnected. Remaining connections: {len(self.user_connections[user_id])}")
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific user's WebSocket connections"""
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"[WebSocket] Error sending to user {user_id}: {e}")

manager = ConnectionManager()


async def broadcast_cabin_update(cabin_id: str, status: str, **kwargs):
    payload = {
        "cabinId": cabin_id,
        "status": status
    }
    payload.update(kwargs)
    
    await manager.broadcast({
        "type": "CABIN_UPDATE",
        "payload": payload
    })


async def send_message_notification(user_id: str, message_data: dict):
    """Send new message notification to specific user via WebSocket"""
    await manager.send_to_user(user_id, {
        "type": "NEW_MESSAGE",
        "payload": message_data
    })


async def send_conversation_update(user_id: str, conversation_data: dict):
    """Send conversation update to specific user via WebSocket"""
    await manager.send_to_user(user_id, {
        "type": "CONVERSATION_UPDATE",
        "payload": conversation_data
    })
