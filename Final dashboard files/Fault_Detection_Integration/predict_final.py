import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


ROOT = Path(__file__).resolve().parent

MODEL_PATH = (
    ROOT
    / "model"
    / "FINAL_88_32_MODEL.weights.h5"
)
CLASS_NAMES = [
    "MultiHotSpot",
    "SingleHotSpot",
    "StringOpenCircuit"
]

IMAGE_SIZE = (224, 224)
EXPANSION_PERCENT = 30.0


def build_model():
    base_model = keras.applications.MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(224, 224, 3)
    )

    inputs = keras.Input(shape=(224, 224, 3))

    x = keras.applications.mobilenet_v2.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.2)(x)

    outputs = layers.Dense(
        3,
        activation="softmax"
    )(x)

    model = keras.Model(inputs, outputs)

    model.load_weights(MODEL_PATH)

    return model


def create_context_crop(image, x_c_norm, y_c_norm, w_norm, h_norm):
    img_w, img_h = image.size

    # Convert normalized YOLO coordinates to pixels
    x_c = x_c_norm * img_w
    y_c = y_c_norm * img_h
    w = w_norm * img_w
    h = h_norm * img_h

    # Exact same 30% expansion used during training
    new_w = w * (1 + EXPANSION_PERCENT / 100.0)
    new_h = h * (1 + EXPANSION_PERCENT / 100.0)

    x1 = int(max(0, x_c - new_w / 2))
    y1 = int(max(0, y_c - new_h / 2))

    x2 = int(min(img_w, x_c + new_w / 2))
    y2 = int(min(img_h, y_c + new_h / 2))

    if x2 <= x1 or y2 <= y1:
        raise ValueError("Invalid bounding box.")

    return image.crop((x1, y1, x2, y2))


def predict_crop(model, crop):
    crop = crop.convert("RGB")
    crop = crop.resize(IMAGE_SIZE)

    image_array = np.array(crop, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)

    probabilities = model.predict(
        image_array,
        verbose=0
    )[0]

    predicted_class = int(np.argmax(probabilities))
    confidence = float(probabilities[predicted_class] * 100)

    return predicted_class, confidence, probabilities


def predict_from_yolo(image_path, label_path):
    model = build_model()

    image = Image.open(image_path).convert("RGB")

    with open(label_path, "r") as f:
        lines = f.readlines()

    valid_count = 0

    for idx, line in enumerate(lines):
        parts = line.strip().split()

        if len(parts) < 5:
            continue

        # YOLO format:
        # class_id x_center y_center width height
        x_c_norm = float(parts[1])
        y_c_norm = float(parts[2])
        w_norm = float(parts[3])
        h_norm = float(parts[4])

        crop = create_context_crop(
            image,
            x_c_norm,
            y_c_norm,
            w_norm,
            h_norm
        )

        predicted_class, confidence, probabilities = predict_crop(
            model,
            crop
        )

        valid_count += 1

        print("\n========================================")
        print(f"Fault/Object #{valid_count}")
        print("========================================")
        print(f"Prediction : {CLASS_NAMES[predicted_class]}")
        print(f"Confidence : {confidence:.2f}%")

        print("\nClass probabilities:")
        for name, probability in zip(CLASS_NAMES, probabilities):
            print(f"  {name}: {probability * 100:.2f}%")

    if valid_count == 0:
        print("\nNo valid bounding boxes found in the label file.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Solar PV fault classification using the final 30% context model."
    )

    parser.add_argument(
        "image",
        help="Path to the original solar panel image"
    )

    parser.add_argument(
        "label",
        help="Path to the YOLO label .txt file"
    )

    args = parser.parse_args()

    predict_from_yolo(
        Path(args.image),
        Path(args.label)
    )