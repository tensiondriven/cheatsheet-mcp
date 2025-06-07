#!/usr/bin/env python3
"""
Camera Management MCP Server
Provides PTZ camera controls, screenshot capture, and camera discovery.
Integrates with webcam-ptz executable and imagesnap for comprehensive camera operations.

Tools provided:
- list_cameras: Get list of connected cameras
- take_screenshot: Capture image from specified camera
- ptz_control: Send PTZ commands to camera
- get_camera_status: Get current camera position/settings
"""

import asyncio
import json
import logging
import subprocess
import sys
import os
import tempfile
import base64
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.webcam_ptz_path = "/Users/j/Code/logi-ptz/webcam-ptz/webcam-ptz"
        self.imagesnap_path = "/opt/homebrew/bin/imagesnap"
        self.camera_cache = {}
        self.last_camera_scan = 0
        
    async def _run_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Execute command and return result"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                
                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "exit_code": process.returncode
                }
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout}s",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "exit_code": -1
            }
    
    async def discover_cameras(self) -> Dict[str, Any]:
        """Discover available cameras using system_profiler and imagesnap"""
        try:
            # Get USB camera info
            usb_result = await self._run_command([
                "system_profiler", "SPUSBDataType", "-json"
            ])
            
            # Get imagesnap camera list
            imagesnap_result = await self._run_command([
                self.imagesnap_path, "-l"
            ])
            
            cameras = []
            
            if usb_result["success"]:
                try:
                    usb_data = json.loads(usb_result["stdout"])
                    for item in usb_data.get("SPUSBDataType", []):
                        for device in item.get("_items", []):
                            if self._is_camera_device(device):
                                camera_info = {
                                    "name": device.get("_name", "Unknown Camera"),
                                    "vendor_id": device.get("vendor_id", ""),
                                    "product_id": device.get("product_id", ""),
                                    "type": "USB",
                                    "ptz_capable": self._is_ptz_camera(device)
                                }
                                cameras.append(camera_info)
                except json.JSONDecodeError:
                    pass
            
            # Parse imagesnap output for additional camera names
            if imagesnap_result["success"]:
                for line in imagesnap_result["stdout"].split('\n'):
                    if line.strip() and not line.startswith('Video Devices:'):
                        camera_name = line.strip()
                        # Check if this camera is already in our list
                        if not any(cam["name"] == camera_name for cam in cameras):
                            cameras.append({
                                "name": camera_name,
                                "vendor_id": "",
                                "product_id": "",
                                "type": "Video",
                                "ptz_capable": "PTZ" in camera_name.upper()
                            })
            
            self.camera_cache = {cam["name"]: cam for cam in cameras}
            self.last_camera_scan = asyncio.get_event_loop().time()
            
            return {
                "success": True,
                "cameras": cameras,
                "count": len(cameras)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "cameras": [],
                "count": 0
            }
    
    def _is_camera_device(self, device: Dict) -> bool:
        """Check if USB device is a camera"""
        name = device.get("_name", "").lower()
        camera_keywords = ["camera", "webcam", "usb video", "ptz", "logitech"]
        return any(keyword in name for keyword in camera_keywords)
    
    def _is_ptz_camera(self, device: Dict) -> bool:
        """Check if camera supports PTZ"""
        name = device.get("_name", "").lower()
        vendor_id = device.get("vendor_id", "")
        # Logitech PTZ cameras
        return "ptz" in name or vendor_id == "0x046d"
    
    async def take_screenshot(self, camera_name: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Take screenshot from specified camera"""
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"/tmp/camera_screenshot_{timestamp}.jpg"
            
            # Kill any blocking processes first
            await self._run_command(["sudo", "pkill", "cameracaptured"])
            
            # Take screenshot with imagesnap
            result = await self._run_command([
                self.imagesnap_path, "-d", camera_name, output_path
            ], timeout=10)
            
            if result["success"] and os.path.exists(output_path):
                # Read image and encode as base64 for MCP response
                with open(output_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                return {
                    "success": True,
                    "output_path": output_path,
                    "image_data": image_data,
                    "camera_name": camera_name,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Screenshot failed: {result.get('stderr', 'Unknown error')}",
                    "output_path": output_path
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output_path": output_path or ""
            }
    
    async def ptz_control(self, command: str, value: Optional[str] = None) -> Dict[str, Any]:
        """Send PTZ command to camera"""
        try:
            if not os.path.exists(self.webcam_ptz_path):
                return {
                    "success": False,
                    "error": f"webcam-ptz executable not found at {self.webcam_ptz_path}"
                }
            
            # Validate command format
            valid_commands = ["pan", "tilt", "zoom"]
            valid_values = ["min", "max", "middle"]
            
            if not command or command not in valid_commands:
                return {
                    "success": False,
                    "error": f"Invalid command '{command}'. Must be one of: {', '.join(valid_commands)}"
                }
            
            if value is not None:
                # Check if value is numeric (steps) or valid preset
                if not (value in valid_values or (value.lstrip('-').isdigit())):
                    return {
                        "success": False,
                        "error": f"Invalid value '{value}'. Must be one of: {', '.join(valid_values)} or a number of steps"
                    }
                
                # Validate step range for numeric values
                if value.lstrip('-').isdigit():
                    steps = int(value)
                    if abs(steps) > 1000:  # Reasonable limit for safety
                        return {
                            "success": False,
                            "error": f"Step value '{steps}' exceeds safe range (-1000 to 1000)"
                        }
            else:
                return {
                    "success": False,
                    "error": f"Command '{command}' requires a value parameter"
                }
            
            # Kill any blocking processes first
            await self._run_command(["sudo", "pkill", "cameracaptured"])
            
            # Build command
            cmd = [self.webcam_ptz_path, command, value]
            
            result = await self._run_command(cmd, timeout=10)
            
            return {
                "success": result["success"],
                "command": command,
                "value": value,
                "output": result["stdout"],
                "error": result.get("stderr", "") if not result["success"] else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": command,
                "value": value
            }
    
    async def get_camera_status(self) -> Dict[str, Any]:
        """Get current camera status and position"""
        try:
            # For now, just return that we're connected to PTZ camera
            # Could be extended to query actual position if webcam-ptz supports it
            return {
                "success": True,
                "ptz_available": os.path.exists(self.webcam_ptz_path),
                "imagesnap_available": os.path.exists(self.imagesnap_path),
                "last_camera_scan": self.last_camera_scan,
                "cached_cameras": len(self.camera_cache)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

class CameraMCPServer:
    def __init__(self):
        self.camera_manager = CameraManager()
    
    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol request"""
        try:
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "list_cameras":
                result = await self.camera_manager.discover_cameras()
                return {"result": result}
            
            elif method == "take_screenshot":
                camera_name = params.get("camera_name", "PTZ Pro Camera")
                output_path = params.get("output_path")
                result = await self.camera_manager.take_screenshot(camera_name, output_path)
                return {"result": result}
            
            elif method == "ptz_control":
                command = params.get("command", "")
                value = params.get("value")
                
                if not command:
                    return {
                        "error": {"code": -1, "message": "No PTZ command provided"}
                    }
                
                result = await self.camera_manager.ptz_control(command, value)
                return {"result": result}
            
            elif method == "get_camera_status":
                result = await self.camera_manager.get_camera_status()
                return {"result": result}
            
            else:
                return {
                    "error": {"code": -1, "message": f"Unknown method: {method}"}
                }
                
        except Exception as e:
            return {
                "error": {"code": -1, "message": str(e)}
            }

async def main():
    """Main Camera MCP server loop"""
    server = CameraMCPServer()
    
    print("Camera Management MCP Server starting...", file=sys.stderr)
    print("Available tools: list_cameras, take_screenshot, ptz_control, get_camera_status", file=sys.stderr)
    
    # Read JSON-RPC messages from stdin
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            
            if not line:
                break
                
            request = json.loads(line.strip())
            response = await server.handle_mcp_request(request)
            
            # Add request ID if present
            if "id" in request:
                response["id"] = request["id"]
            
            print(json.dumps(response))
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            error_response = {
                "error": {"code": -32700, "message": "Parse error"}
            }
            print(json.dumps(error_response))
            sys.stdout.flush()
            
        except Exception as e:
            error_response = {
                "error": {"code": -1, "message": str(e)}
            }
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())