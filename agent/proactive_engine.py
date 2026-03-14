import threading
import time
from typing import Callable
import uuid

class ProactiveEngine:
    def __init__(self, speak_callback: Callable[[str], None]):
        """
        Engine that runs side-by-side with the main JarvisLive instance.
        It manages a list of scheduled alerts and triggers JARVIS to speak them autonomously.
        """
        self.speak = speak_callback
        self.tasks = []
        self._lock = threading.Lock()
        
        # Start background worker
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print("[ProactiveEngine] ⏰ Engine initialized.")

    def schedule(self, delay_minutes: float, instruction: str) -> str:
        """Schedules a proactive alert/speech from JARVIS."""
        trigger_time = time.time() + (delay_minutes * 60)
        task_id = str(uuid.uuid4())[:8]
        
        with self._lock:
            self.tasks.append({
                "id": task_id,
                "trigger_time": trigger_time,
                "instruction": instruction
            })
            
        print(f"[ProactiveEngine] 🕒 Scheduled '{instruction}' in {delay_minutes} minutes.")
        return f"Proactive alert scheduled successfully for {delay_minutes} minutes from now."

    def _worker(self):
        while True:
            time.sleep(2)  # Check every 2 seconds
            
            now = time.time()
            triggered_tasks = []
            
            with self._lock:
                for task in self.tasks:
                    if now >= task["trigger_time"]:
                        triggered_tasks.append(task)
                        
                for t in triggered_tasks:
                    self.tasks.remove(t)
                    
            # Process triggered tasks outside the lock to avoid blocking
            for task in triggered_tasks:
                try:
                    instruction = task["instruction"]
                    print(f"[ProactiveEngine] 🚨 Triggering alert: {instruction}")
                    
                    # We pass the instruction straight to the voice engine. 
                    # Optionally, we could run it through the LLM first to "think" about how to say it,
                    # but for basic reminders, passing the instruction directly works well and is instant.
                    self.speak(instruction)
                    
                except Exception as e:
                    print(f"[ProactiveEngine] ⚠️ Error triggering alert: {e}")
