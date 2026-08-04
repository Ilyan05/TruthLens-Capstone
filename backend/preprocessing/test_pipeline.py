from backend.preprocessing.pipeline import preprocess

print(preprocess("sample.txt"))
print("-" * 40)
print(preprocess("test_image.jpg"))
print("-" * 40)
print(preprocess("test_audio.mp3"))