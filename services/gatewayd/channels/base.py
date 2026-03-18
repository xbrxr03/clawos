"""Base channel interface."""
class BaseChannel:
    async def start(self): pass
    async def stop(self): pass
    async def send(self, recipient: str, message: str): raise NotImplementedError
    def health(self) -> dict: return {"status": "ok"}
