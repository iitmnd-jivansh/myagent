from kokoro import KPipeline
import soundfile as sf
import numpy as np


print("Loading Kokoro...")

pipeline = KPipeline(lang_code='a')

print("Kokoro loaded.")


def generate_speech(text, output_path="response.wav"):

    print("Generating speech...")

    generator = pipeline(
        text,
        voice='af_heart'
    )

    all_audio = []

    for i, (gs, ps, audio) in enumerate(generator):

        all_audio.append(audio)

    final_audio = np.concatenate(all_audio)

    sf.write(
        output_path,
        final_audio,
        24000
    )

    print("Speech generated.")

    return output_path
