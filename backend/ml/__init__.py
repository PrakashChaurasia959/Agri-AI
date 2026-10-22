"""Machine learning package for AgriVision AI.

Modules
-------
``config``           training / inference hyper-parameters and paths
``preprocessing``    image validation and normalisation
``model_registry``   lazy loading and status reporting for model artifacts
``predict``          disease classification inference
``crop_predictor``   crop recommendation inference
``yield_predictor``  crop yield regression inference
``disease_knowledge``educational information per disease class
``evaluation``       classification and regression metrics
``train_cnn``        MobileNetV2 disease classifier training pipeline
``train_crop_model`` crop recommendation training pipeline
``train_yield_model``crop yield regression training pipeline
"""

__all__ = [
    "config",
    "crop_predictor",
    "disease_knowledge",
    "evaluation",
    "model_registry",
    "predict",
    "preprocessing",
    "train_cnn",
    "train_crop_model",
    "train_yield_model",
    "yield_predictor",
]
