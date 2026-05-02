#!/usr/bin/env python3
"""
ONNX Model Inspector
Analyzes the 3 depression detection ONNX models to extract:
- Input names and types
- Output names and types  
- Input shapes
"""

import onnx
import sys
from pathlib import Path

def inspect_model(model_path):
    """Inspect ONNX model structure"""
    try:
        model = onnx.load(model_path)
        graph = model.graph
        
        print(f"\n{'='*70}")
        print(f"Model: {Path(model_path).name}")
        print(f"{'='*70}")
        
        # Inputs
        print("\n📥 INPUTS:")
        for input_tensor in graph.input:
            name = input_tensor.name
            dtype = input_tensor.type.tensor_type.elem_type
            shape = [d.dim_value if d.dim_value > 0 else '?' 
                    for d in input_tensor.type.tensor_type.shape.dim]
            dtype_name = onnx.TensorProto.DataType.Name(dtype)
            print(f"  - Name: '{name}'")
            print(f"    Type: {dtype_name} ({dtype})")
            print(f"    Shape: {shape}")
            
        # Outputs
        print("\n📤 OUTPUTS:")
        for output_tensor in graph.output:
            name = output_tensor.name
            dtype = output_tensor.type.tensor_type.elem_type
            shape = [d.dim_value if d.dim_value > 0 else '?' 
                    for d in output_tensor.type.tensor_type.shape.dim]
            dtype_name = onnx.TensorProto.DataType.Name(dtype)
            print(f"  - Name: '{name}'")
            print(f"    Type: {dtype_name} ({dtype})")
            print(f"    Shape: {shape}")
            
        # Initializers (weights)
        print(f"\n⚙️  PARAMETERS: {len(graph.initializer)} weight tensors")
        
        return True
    except Exception as e:
        print(f"❌ Error inspecting {model_path}: {e}")
        return False

if __name__ == '__main__':
    models_dir = Path(__file__).parent / 'asset' / 'models'
    
    models = [
        'model_quantized.onnx',
        'module2_lstm.onnx', 
        'module3_fusion.onnx'
    ]
    
    print("\n🔍 ONNX Model Inspection Report")
    print(f"Location: {models_dir}")
    
    for model_name in models:
        model_path = models_dir / model_name
        if model_path.exists():
            inspect_model(str(model_path))
        else:
            print(f"\n⚠️  Model not found: {model_path}")
    
    print("\n" + "="*70)
    print("✅ Inspection Complete")
