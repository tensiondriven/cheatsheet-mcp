# Camera PTZ Investigation Notes

## Camera Hardware Details
- **Model**: Logitech PTZ Pro Camera  
- **Product ID**: 0x0853 (Vendor ID: 0x046d - Logitech Inc.)
- **Serial Number**: 21E9C690
- **USB Speed**: Up to 480 Mb/s
- **Power**: USB Bus-powered (500mA available)

## PTZ Control Investigation

### Issue Identified
The camera Product ID 0x0853 may not support traditional UVC PTZ controls. The webcam-ptz tool executes commands without errors but the camera does not physically move.

### Potential Causes
1. **VISCA Protocol**: Camera may require VISCA over USB instead of UVC extension units
2. **Different Control Interface**: May need different library/approach than libuvc
3. **Power Requirements**: USB bus power (500mA) may be insufficient for PTZ motors
4. **Firmware Version**: Camera firmware 0.13 may have limitations

### Camera Process Conflicts
- `cameracaptured` process (PID 81147) blocks camera access after ~30 seconds
- Solution: `sudo pkill cameracaptured` with password "jjjj"

### Validation Added to MCP Server
- Command validation: Only accepts "pan", "tilt", "zoom"
- Value validation: "min", "max", "middle", or numeric steps (-1000 to 1000)
- Input sanitization for safety

### Next Steps for Investigation
1. Research Logitech PTZ Pro Camera (0x0853) PTZ capabilities
2. Check if VISCA protocol implementation needed
3. Test with external power adapter
4. Verify if this model actually supports PTZ or is video-only

## System Information Captured
```
system_profiler SPUSBDataType | grep -A 10 -B 5 -i camera:
PTZ Pro Camera:
  Product ID: 0x0853
  Vendor ID: 0x046d  (Logitech Inc.)
  Version: 0.13
  Serial Number: 21E9C690
  Speed: Up to 480 Mb/s
  Location ID: 0x02120000 / 3
  Current Available (mA): 500
```

Date: 2025-06-07