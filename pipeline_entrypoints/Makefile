.PHONY: install train predict clean

MODEL_PATH = models/titanic_survival_pipeline.joblib
INPUT_CSV ?= pasajeros.csv
OUTPUT_CSV ?= predicciones.csv

install:
	pip install -e .

train:
	titanic-train --model-path $(MODEL_PATH)

predict:
	titanic-predict $(INPUT_CSV) --model-path $(MODEL_PATH) --output-csv $(OUTPUT_CSV)

clean:
	rm -rf build dist *.egg-info models predicciones.csv
