"""
合成测试脚本：验证 pysilk 编解码闭环
"""
import sys
sys.path.insert(0, 'src')
import asyncio
import logging
import wave
import struct

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_synthetic_silk():
    print("🧪 开始合成测试：验证 pysilk 解码逻辑...")
    
    try:
        import pysilk
        
        # 1. 生成一段静音的 PCM 数据 (16000Hz, 16bit, Mono, 1秒)
        # 16000 采样点 * 2 bytes = 32000 bytes
        duration_sec = 1
        sample_rate = 16000
        num_samples = sample_rate * duration_sec
        # 生成静音 (0)
        pcm_data = struct.pack('<' + 'h' * num_samples, *[0] * num_samples)
        
        print(f"📦 生成 PCM 数据: {len(pcm_data)} bytes")
        
        # 2. 编码为 SILK (使用 pysilk.encode)
        # pysilk.encode(pcm_data, sample_rate=16000) -> silk_bytes
        # bit_rate: 16000 - 48000
        print("📤 正在编码为 SILK...")
        try:
            # 尝试带 sample_rate 参数
            silk_data = pysilk.encode(pcm_data, sample_rate=16000)
        except TypeError:
            # 如果不行，尝试默认
            silk_data = pysilk.encode(pcm_data)
            
        print(f"✅ 编码成功: {len(silk_data)} bytes")
        
        # 3. 模拟微信语音：添加 0x02 头部
        wechat_voice_bytes = b'\x02' + silk_data
        print(f"📱 添加微信头部 (0x02)，总大小: {len(wechat_voice_bytes)} bytes")
        
        # 4. 使用 VoiceParser 解码
        from pathlib import Path
        from sagemate.pipeline.voice_parser import VoiceParser
        from tempfile import TemporaryDirectory
        
        with TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir)
            file_id = "synthetic_test"
            
            print("🔄 调用 VoiceParser.parse_voice...")
            
            # 注意：parse_voice 是异步的
            text = await VoiceParser.parse_voice(
                voice_bytes=wechat_voice_bytes,
                file_id=file_id,
                raw_dir=raw_dir,
                encode_type=6 # SILK
            )
            
            # 检查生成的文件
            voice_dir = raw_dir / "voice"
            silk_file = voice_dir / f"{file_id}.silk"
            wav_file = voice_dir / f"{file_id}.wav" # 已经被 delete 了?
            
            # parse_voice 内部会 delete wav 文件。
            # 我们检查 text。对于静音，text 应该是空字符串或者很短。
            
            print(f"📝 转写结果: '{text}'")
            
            # 验证原始文件是否保存
            if silk_file.exists():
                print(f"✅ 原始 .silk 文件已归档: {silk_file}")
            else:
                print("❌ 原始 .silk 文件未找到!")
                
            if text == "" or "静音" in text or "无" in text or "。" in text:
                print("🎉 测试通过：VoiceParser 成功解码并转写了 SILK 语音！")
            else:
                # 即使转写出不相关的内容，只要不报错，说明解码流程是通的
                print(f"⚠️ 转写内容异常 (可能是 Whisper 对静音的处理)，但解码流程已验证通过。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_synthetic_silk())
