"""
Модуль для решения капчи
"""
import aiohttp
import asyncio
from typing import Optional
from config import ANTICAPTCHA_API_KEY, ANTICAPTCHA_ENABLED


class AntiCaptcha:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or ANTICAPTCHA_API_KEY
        self.enabled = ANTICAPTCHA_ENABLED and bool(self.api_key)
        self.base_url = "https://api.2captcha.com"
        
    async def solve_captcha(self, image_url: str = None, image_base64: str = None,
                          captcha_type: str = "ImageToTextTask") -> Optional[str]:
        """
        Решить капчу через 2captcha
        """
        if not self.enabled:
            return None
        
        try:
            # Создание задачи
            async with aiohttp.ClientSession() as session:
                data = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": captcha_type,
                    }
                }
                
                if image_url:
                    data["task"]["body"] = image_url
                elif image_base64:
                    data["task"]["body"] = image_base64
                else:
                    return None
                
                # Отправка задачи
                async with session.post(
                    f"{self.base_url}/createTask",
                    json=data
                ) as response:
                    result = await response.json()
                    if result.get("errorId") != 0:
                        return None
                    
                    task_id = result.get("taskId")
                    if not task_id:
                        return None
                    
                    # Ожидание решения (максимум 2 минуты)
                    for _ in range(40):  # 40 попыток по 3 секунды = 2 минуты
                        await asyncio.sleep(3)
                        
                        async with session.post(
                            f"{self.base_url}/getTaskResult",
                            json={
                                "clientKey": self.api_key,
                                "taskId": task_id
                            }
                        ) as check_response:
                            check_result = await check_response.json()
                            
                            if check_result.get("status") == 1:  # Решено
                                return check_result.get("solution", {}).get("text")
                            elif check_result.get("errorId") != 0:
                                return None
                    
                    return None
                    
        except Exception as e:
            print(f"Ошибка при решении капчи: {e}")
            return None
    
    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        """
        Решить reCAPTCHA v2
        """
        if not self.enabled:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                # Создание задачи
                data = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": "RecaptchaV2TaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": site_key
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/createTask",
                    json=data
                ) as response:
                    result = await response.json()
                    if result.get("errorId") != 0:
                        return None
                    
                    task_id = result.get("taskId")
                    if not task_id:
                        return None
                    
                    # Ожидание решения
                    for _ in range(40):
                        await asyncio.sleep(3)
                        
                        async with session.post(
                            f"{self.base_url}/getTaskResult",
                            json={
                                "clientKey": self.api_key,
                                "taskId": task_id
                            }
                        ) as check_response:
                            check_result = await check_response.json()
                            
                            if check_result.get("status") == 1:
                                return check_result.get("solution", {}).get("gRecaptchaResponse")
                            elif check_result.get("errorId") != 0:
                                return None
                    
                    return None
                    
        except Exception as e:
            print(f"Ошибка при решении reCAPTCHA: {e}")
            return None


# Глобальный экземпляр
anticaptcha = AntiCaptcha()


