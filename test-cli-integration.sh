#!/usr/bin/env python3
"""
业务指标集成测试

测试指标采集器在实际CLI中的集成
"""

import sys
import os
from pathlib import Path

# 测试Minerva CLI集成
def test_minerva_cli_integration():
    """测试Minerva CLI中的指标采集"""
    print("=== 测试Minerva CLI指标集成 ===")
    
    # 测试研究命令
    os.chdir("/Users/xiamingxing/Workspace/minerva")
    
    # 先尝试安装metrics模块
    print("\n1. 安装metrics模块到minerva...")
    exit_code = os.system("pip install -e .")
    
    if exit_code != 0:
        print("❌ metrics模块安装失败")
        return False
    
    # 测试研究指标采集
    print("\n2. 测试研究指标采集:")
    exit_code = os.system('python3 -c "from minerva.metrics import get_all_metrics; print(get_all_metrics())"')
    
    if exit_code != 0:
        print("❌ 研究指标测试失败")
        return False
    
    return True


# 测试Agora CLI集成
def test_agora_cli_integration():
    """测试Agora CLI中的指标采集"""
    print("\n=== 测试Agora CLI指标集成 ===")
    
    # 测试Pipeline指标采集
    os.chdir("/Users/xiamingxing/Workspace/agora")
    
    # 先尝试安装metrics模块
    print("\n3. 安装metrics模块到agora...")
    exit_code = os.system("pip install -e .")
    
    if exit_code != 0:
        print("❌ metrics模块安装失败")
        return False
    
    # 测试Pipeline指标采集
    print("\n4. 测试Pipeline指标采集:")
    exit_code = os.system('python3 -c "from agora.metrics import get_all_pipeline_metrics; print(get_all_pipeline_metrics())"')
    
    if exit_code != 0:
        print("❌ Pipeline指标测试失败")
        return False
    
    return True


# 主测试
def main():
    print("🧪 CLI指标集成功能验证")
    print(f"测试时间: 2026-05-24")
    print("="*60)
    
    results = {}
    
    # 测试Minerva CLI集成
    print("测试1/2: Minerva CLI指标集成")
    results["minerva_cli"] = test_minerva_cli_integration()
    
    # 测试Agora CLI集成
    print("\n测试2/2: Agora CLI指标集成")
    results["agora_cli"] = test_agora_cli_integration()
    
    print("\n" + "="*60)
    print("📊 集成测试结果:")
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print("")
    
    if all_passed:
        print("🎉 CLI指标集成验证通过！")
        print("\n下一步:")
        print("   - 验证实际CLI命令")
        print("   - 配置定期监控任务")
        print("   - 设置告警通知")
    else:
        print("⚠️ 部分验证失败，请检查:")
        print("   - 依赖是否满足")
        print("   - 集成是否正确")
        print("   - 配置是否需要调整")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
