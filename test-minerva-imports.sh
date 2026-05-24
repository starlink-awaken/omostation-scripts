#!/usr/bin/env python3
"""
测试minerva模块导入是否正常工作
"""

def test_imports():
    """测试所有指标相关的导入"""
    print("=== 测试Minerva模块导入 ===")
    
    test_cases = [
        ("from minerva.metrics import get_all_metrics", "get_all_metrics函数"),
        ("from minerva.metrics import BusinessMetricsCollector", "BusinessMetricsCollector类"),
        ("from minerva.metrics.collector import BusinessMetricsCollector", "带路径的导入"),
        ("from minerva.metrics.collector import get_metrics_collector", "get_metrics_collector函数"),
    ]
    
    all_passed = True
    for test_case, description in test_cases:
        try:
            print(f"  {description}")
            exec(test_case)
            print(f"    ✅ {description} 通过")
        except ImportError as e:
            print(f"    ❌ {description} 失败: {e}")
            all_passed = False
        except Exception as e:
            print(f"    ❌ {description} 失败: {e}")
            all_passed = False
    
    return all_passed


def test_class_instantiation():
    """测试类实例化"""
    print("\n=== 测试类实例化 ===")
    
    test_cases = [
        ("from minerva.metrics.collector import BusinessMetricsCollector", "BusinessMetricsCollector类实例"),
        ("from minerva.metrics.collector import PipelineMetricsCollector", "PipelineMetricsCollector类实例"),
    ]
    
    all_passed = True
    for test_case, description in test_cases:
        try:
            print(f"  {description}")
            exec(test_case)
            print(f"    ✅ {description} 通过")
        except Exception as e:
            print(f"    ❌ {description} 失败: {e}")
            all_passed = False
    
    return all_passed


def main():
    """主测试函数"""
    print("🧪 Minerva模块导入和实例化测试")
    print(f"测试时间: {datetime.now().isoformat()}")
    print("="*60)
    print("")
    
    results = {}
    
    # 测试导入
    print("测试1/2: 模块导入")
    results["imports"] = test_imports()
    
    # 测试类实例化
    print("\n测试2/2: 类实例化")
    results["instantiation"] = test_class_instantiation()
    
    print("\n" + "="*60)
    print("📊 测试结果:")
    for test_type, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_type}: {status}")
    
    all_passed = all(results.values())
    print("")
    
    if all_passed:
        print("🎉 所有导入和实例化测试通过！")
        print("\n下一步:")
        print("   - 验证其他模块导入")
        print("   - 集成端到端测试")
        print("   - 验证CLI功能")
    else:
        print("⚠️  部分测试失败，需要检查模块路径和依赖")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
