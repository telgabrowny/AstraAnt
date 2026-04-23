# Simulation, Robot codes and Figure data from Collective phototactic robotectonics

[https://doi.org/10.5061/dryad.05qfttfb2](https://doi.org/10.5061/dryad.05qfttfb2)

This dataset contains A) simulation codes, B) programs encoded in the robots, C) figure data and the calculation criteria for trapping of single and multiple agents in the article Giardina, Prasath et al. ([https://doi.org/10.48550/arXiv.2208.12373](https://doi.org/10.48550/arXiv.2208.12373).

## Description of the data and file structure

There are three folders in the dataset: a) Figs, b) Code, c) Self-Trapping.

a) Figs Folder: The Figs folder contains all the data used to generate the plots in the main-article. There is a sub-folder titled Data which has the raw data of the plots in .txt/.csv format and is used inside the Figs.ipynb, a python notebook with detailed description as well as the plots used in the article.

b) Code folder: This folder has 5 sub-folders each with Arduino IDE code (inside base/) for each robot to perform 1) Construction, 2) de-construction, 3) no gradient descent (dynamics without photormone following behavior), 4) no threshold (dynamics when there is no threshold for deposition of substrate elements), 5) pseudocode containing the algorithm of the code (also detailed in the main-article).

c) Self-trapping: Inside this folder there are 2 sub-folders: Calculation, Dynamic-trapping. 1) Calculation folder contains the Mathematica notebooks used to analyze the different asymptotic limits of self-trapping (detailed in the main-article as well as the supplementary materials). 2) Dynamic-trapping folder contains the Matlab code to simulation an agent following its photormone trail, the dynamics of which is solved using a finite-difference technique.