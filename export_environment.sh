#!/usr/bin/env bash
conda activate nemde
rm environment.yml
conda env export > environment.yml