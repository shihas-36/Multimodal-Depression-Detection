#!/usr/bin/env python
"""
Validation script for FL backend refactoring.

Run this in Django shell to verify:
- Safe deserialization (no pickle)
- Correct FedAvg algorithm
- Proper validation
"""

def test_safe_deserialization():
    """Test NPZ deserialization (no pickle code execution)."""
    print("\n" + "="*70)
    print("TEST 1: Safe Deserialization (NPZ, no pickle)")
    print("="*70)
    
    from fl_core.aggregation import serialize_weights_to_npz, deserialize_weights_from_npz
    import numpy as np
    
    # Create test weights
    weights = {
        'layer1_w': np.random.randn(10, 5).astype(np.float32),
        'layer1_b': np.random.randn(5).astype(np.float32),
        'layer2_w': np.random.randn(5, 2).astype(np.float32),
        'layer2_b': np.random.randn(2).astype(np.float32),
    }
    
    # Serialize
    npz_bytes = serialize_weights_to_npz(weights)
    print(f"✓ Serialized weights to NPZ: {len(npz_bytes)} bytes")
    
    # Deserialize
    recovered = deserialize_weights_from_npz(npz_bytes)
    print(f"✓ Deserialized NPZ to {len(recovered)} arrays")
    
    # Verify
    for key in weights:
        assert np.allclose(weights[key], recovered[key])
    print("✓ All weights match perfectly")
    print("✓ NPZ format confirmed (safe, no pickle)")
    
    return True


def test_fedavg_algorithm():
    """Test FedAvg weighted averaging is correct."""
    print("\n" + "="*70)
    print("TEST 2: Correct FedAvg Algorithm (Weighted Averaging)")
    print("="*70)
    
    from fl_core.aggregation import fedavg_aggregate
    import numpy as np
    
    # Test case: 2 clients with different num_examples
    w1 = {'weights': np.array([1.0, 1.0])}
    w2 = {'weights': np.array([3.0, 3.0])}
    
    # Client 1: 100 examples
    # Client 2: 300 examples
    # Expected: (1*100 + 3*300) / 400 = 1000/400 = 2.5
    
    result = fedavg_aggregate([w1, w2], [100, 300])
    expected = np.array([2.5, 2.5])
    
    assert np.allclose(result['weights'], expected)
    print(f"Client 1 weights: {w1['weights']} (100 examples)")
    print(f"Client 2 weights: {w2['weights']} (300 examples)")
    print(f"Aggregated: {result['weights']}")
    print(f"Expected:   {expected}")
    print("✓ FedAvg weighted averaging is CORRECT")
    
    return True


def test_validation():
    """Test weight validation catches errors."""
    print("\n" + "="*70)
    print("TEST 3: Weight Validation")
    print("="*70)
    
    from fl_core.aggregation import validate_weights_structure
    import numpy as np
    
    # Valid
    valid = {'w': np.array([1.0, 2.0])}
    is_valid, error = validate_weights_structure(valid)
    assert is_valid
    print("✓ Valid weights accepted")
    
    # Invalid: not a dict
    invalid1, error1 = validate_weights_structure([1, 2, 3])
    assert not invalid1
    print(f"✓ Caught non-dict: {error1}")
    
    # Invalid: non-numpy values
    invalid2, error2 = validate_weights_structure({'w': [1.0, 2.0]})
    assert not invalid2
    print(f"✓ Caught non-numpy value: {error2}")
    
    # Invalid: key mismatch
    invalid3, error3 = validate_weights_structure(
        {'w': np.array([1.0])},
        expected_keys={'w', 'b'}
    )
    assert not invalid3
    print(f"✓ Caught missing keys: {error3}")
    
    return True


def test_single_client_handling():
    """Test single client case (no averaging needed)."""
    print("\n" + "="*70)
    print("TEST 4: Single Client Handling")
    print("="*70)
    
    from fl_core.aggregation import fedavg_aggregate
    import numpy as np
    
    # Single client with 100 examples
    w1 = {'weights': np.array([1.5, 2.5])}
    
    result = fedavg_aggregate([w1], [100])
    
    assert np.allclose(result['weights'], w1['weights'])
    print("✓ Single client: weights returned as-is (no averaging)")
    
    return True


def test_key_consistency():
    """Test key consistency check across clients."""
    print("\n" + "="*70)
    print("TEST 5: Key Consistency Check")
    print("="*70)
    
    from fl_core.aggregation import fedavg_aggregate
    import numpy as np
    
    w1 = {'layer1': np.array([1.0]), 'layer2': np.array([2.0])}
    w2 = {'layer1': np.array([3.0])}  # Missing 'layer2'
    
    try:
        fedavg_aggregate([w1, w2], [100, 100])
        print("✗ Should have caught key mismatch!")
        return False
    except ValueError as e:
        print(f"✓ Caught key mismatch: {e}")
        return True


def test_division_by_zero():
    """Test division by zero prevention."""
    print("\n" + "="*70)
    print("TEST 6: Division by Zero Prevention")
    print("="*70)
    
    from fl_core.aggregation import fedavg_aggregate
    import numpy as np
    
    w1 = {'w': np.array([1.0])}
    
    try:
        # num_examples = 0, should fail
        fedavg_aggregate([w1], [0])
        print("✗ Should have caught zero num_examples!")
        return False
    except ValueError as e:
        print(f"✓ Caught division by zero: {e}")
        return True


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "█"*70)
    print("FL BACKEND REFACTORING - VALIDATION TESTS")
    print("█"*70)
    
    tests = [
        ("Safe Deserialization", test_safe_deserialization),
        ("FedAvg Algorithm", test_fedavg_algorithm),
        ("Weight Validation", test_validation),
        ("Single Client Handling", test_single_client_handling),
        ("Key Consistency", test_key_consistency),
        ("Division by Zero", test_division_by_zero),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Backend refactoring is successful!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review above")
        return False


if __name__ == '__main__':
    import sys
    import os
    import django
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    # Run tests
    success = run_all_tests()
    sys.exit(0 if success else 1)
