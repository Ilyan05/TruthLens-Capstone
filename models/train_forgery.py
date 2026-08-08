import os


DATA_DIR = "data/forgery_dataset"
OUT = "models/forgery_model.h5"

IMG = 224
BATCH = 32
EPOCHS = 6


def main():
    import tensorflow as tf
    from tensorflow.keras import layers, models
    from tensorflow.keras.applications import MobileNetV2

    td = os.path.join(DATA_DIR, "train")
    vd = os.path.join(DATA_DIR, "val")

    if not os.path.isdir(td):
        print(
            f"[!] Dataset not found at {td}. "
            "Create train/{real,fake} and val/{real,fake} first."
        )
        return

    train = tf.keras.utils.image_dataset_from_directory(
        td,
        image_size=(IMG, IMG),
        batch_size=BATCH,
        label_mode="binary"
    )

    val = tf.keras.utils.image_dataset_from_directory(
        vd,
        image_size=(IMG, IMG),
        batch_size=BATCH,
        label_mode="binary"
    )

    norm = layers.Rescaling(1.0 / 255)

    base = MobileNetV2(
        input_shape=(IMG, IMG, 3),
        include_top=False,
        weights="imagenet"
    )
    base.trainable = False

    inp = layers.Input(shape=(IMG, IMG, 3))

    x = norm(inp)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)

    out = layers.Dense(
        1,
        activation="sigmoid"
    )(x)

    model = models.Model(inp, out)

    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy"]
    )

    def relabel(img, y):
        return img, 1.0 - y  # 1 = fake

    train = train.map(relabel)
    val = val.map(relabel)

    model.fit(
        train,
        validation_data=val,
        epochs=EPOCHS
    )

    os.makedirs(
        "models",
        exist_ok=True
    )

    model.save(OUT)

    print(
        f"[OK] Saved {OUT} (output = P(fake))"
    )


if __name__ == "__main__":
    main()