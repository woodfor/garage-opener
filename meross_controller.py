# meross_controller.py

import asyncio
import os
import time
from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus, Namespace
from dotenv import load_dotenv
from util import write_log_to_txt
from datetime import datetime

class MerossGarageController:
    def __init__(self, email: str, password: str, device_name: str, cooldown_seconds=120):
        if not email or not password or not device_name:
            raise ValueError("Meross email, password, and device name must be provided.")
        self.email = email
        self.password = password
        self.device_name = device_name
        self.http_client = None
        self.manager = None
        self.garage_device = None
        self._initialized_successfully = False # Renamed for clarity
        
        # Cooldown management
        self.last_open_time = 0.0
        self.cooldown_seconds = cooldown_seconds

    async def initialize(self) -> bool:
        """
        Initializes the connection to Meross cloud, discovers devices,
        and selects the target garage door.
        Returns True if initialization was successful and device is ready, False otherwise.
        """
        if self._initialized_successfully and self.garage_device and self.garage_device.online_status == OnlineStatus.ONLINE:
            print("Meross controller already initialized and device is online.")
            return True

        try:
            print(f"Attempting to authenticate with Meross email: {self.email}...")
            self.http_client = await MerossHttpClient.async_from_user_password(email=self.email, password=self.password, api_base_url="https://iotx-us.meross.com")
            print("Authenticated successfully. Initializing manager and discovering devices...")
            self.manager = MerossManager(http_client=self.http_client)
            await self.manager.async_init()
            await self.manager.async_device_discovery()
            
            devices = self.manager.find_devices()
            if not devices:
                print("No Meross devices found on your account.")
                await self.close_connection()
                self._initialized_successfully = False
                return False

            found_device = None
            print("\nAvailable online devices:")
            for dev in devices:
                if dev.online_status == OnlineStatus.ONLINE:
                    print(f"  - Name: '{dev.name}', Type: '{dev.type}', UUID: '{dev.uuid}'")
                    if hasattr(dev, 'name') and dev.name == self.device_name:
                        found_device = dev
                        break
            
            if found_device:
                self.garage_device = found_device
                print(f"Successfully found and selected garage door: '{self.garage_device.name}'")
                self._initialized_successfully = True
                return True
            else:
                print(f"Could not find an online garage door named '{self.device_name}' with required capabilities.")
                await self.close_connection()
                self._initialized_successfully = False
                return False
                
        except Exception as e:
            print(f"Error during Meross initialization: {e}")
            await self.close_connection()
            self._initialized_successfully = False
            return False

    async def _ensure_initialized(self) -> bool:
        """Checks if initialized and device is online, re-initializes if necessary."""
        if not self._initialized_successfully or \
           self.garage_device is None or \
           self.garage_device.online_status != OnlineStatus.ONLINE:
            print("Controller not initialized or device offline. Attempting to initialize...")
            return await self.initialize()
        
        # Additional session health check
        try:
            # Try a simple operation to verify session is still valid
            if hasattr(self.garage_device, 'get_status'):
                await self.garage_device.async_get_status()
        except Exception as e:
            print(f"Session health check failed: {e}. Re-initializing...")
            self._initialized_successfully = False
            return await self.initialize()
        
        return True

    def _can_open_door(self) -> bool:
        """Check if enough time has passed since last door open."""
        if self.last_open_time <= 0:
            return True
        return (time.monotonic() - self.last_open_time) >= self.cooldown_seconds
    
    def _record_door_open(self):
        """Record the current time as when the door was opened."""
        self.last_open_time = time.monotonic()

    async def open_door(self) -> bool:
        """Sends the 'open' command to the garage door with cooldown check."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check cooldown first
        if not self._can_open_door():
            print(f"Door open request ignored: still within {self.cooldown_seconds}s cooldown period.")
            return False
        
        if not await self._ensure_initialized():
            print("Cannot open door: Meross client not ready.")
            write_log_to_txt(f"{current_time} Cannot open door: Meross client not ready.")
            return False
        
        try:
            print(f"Sending 'open' command to '{self.garage_device.name}'...")
            await self.garage_device.async_open(channel=0) # open=1 for open
            print(f"'{self.garage_device.name}' open command sent.")
            # Record the successful open for cooldown
            self._record_door_open()
            return True
        except Exception as e:
            print(f"Error opening garage door '{self.garage_device.name}': {e}")
            write_log_to_txt(f"{current_time} Error opening garage door '{self.garage_device.name}': {e}")
            self._initialized_successfully = False # Mark for re-initialization on next call
            return False

    async def close_door(self) -> bool:
        """Sends the 'close' command to the garage door."""
        if not await self._ensure_initialized():
            print("Cannot close door: Meross client not ready.")
            return False

        try:
            print(f"Sending 'close' command to '{self.garage_device.name}'...")
            await self.garage_device.async_close(channel=0) # open=0 for close
            print(f"'{self.garage_device.name}' close command sent.")
            return True
        except Exception as e:
            print(f"Error closing garage door '{self.garage_device.name}': {e}")
            self._initialized_successfully = False # Mark for re-initialization on next call
            return False

    async def close_connection(self):
        """Logs out from Meross cloud and cleans up resources."""
        if self.manager:
            print("Closing Meross connection and logging out...")
            try:
                self.manager.close()
                await self.http_client.async_logout()
                print("Successfully logged out from Meross.")
            except Exception as e:
                print(f"Error during Meross logout: {e}")
        self.garage_device = None
        self.manager = None
        self.http_client = None
        self._initialized_successfully = False
    
    # async def is_door_open(self) -> bool:
    #     """Checks if the garage door is open."""
    #     if not await self._ensure_initialized():
    #         print("Cannot check door status: Meross client not ready.")
    #         return False
        
    #     try:
    #         is_open = self.garage_device.get_is_open()
    #         print(f"Garage door status '{self.garage_device.name}': {is_open}")
    #         return self.garage_device.get_is_open()
    #     except Exception as e:
    #         print(f"Error checking garage door status '{self.garage_device.name}': {e}")
    #         return False

# 可选: 添加一个小的测试块，当直接运行此模块文件时执行
async def _test_module():
    load_dotenv() # 加载 .env 文件 (确保 .env 在此文件同目录或项目根目录)
    email = os.environ.get("MEROSS_EMAIL") # 使用环境变量或默认值
    password = os.environ.get("MEROSS_PASSWORD")
    device_name = os.environ.get("MEROSS_GARAGE_DOOR_NAME") # 替换为您的测试设备名称

    if not email or not password or not device_name:
        print("Test credentials not found. Please set MEROSS_EMAIL_TEST and MEROSS_PASSWORD_TEST or edit _test_module.")
        return

    controller = MerossGarageController(email=email, password=password, device_name=device_name)
    
    if await controller.initialize():
        print("\n--- Test: Opening Door ---")
        await controller.open_door()
        # is_open = await controller.is_door_open()
        # print(f"Garage door status: {is_open}")
        
        print("\nWaiting for 40 seconds...")
        await asyncio.sleep(40)
        
        print("\n--- Test: Closing Door ---")
        await controller.close_door()
        
        await controller.close_connection()
    else:
        print("Failed to initialize controller for testing.")

if __name__ == '__main__':
    # 这个 __main__ 块允许您直接运行 python meross_controller.py 来测试模块功能
    print("Running Meross Controller Module Test...")
    asyncio.run(_test_module())
