#Allows relative imports, depends on where this script will end-up
import os, sys, csv
module_path = os.path.abspath(os.path.join('..'))
if module_path not in sys.path:
    sys.path.append(module_path)

import shutil
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import pandas as pd
import pickle 

from src.models import *
from src.preprocessing import *
from src.train_eval_helpers import *
from src.plots import * 
from src.ismart import ismart
#from src.plots import *

import argparse
from src.torch_util import str_to_bool
from datetime import datetime as dt 

def args_parser():
    parser = argparse.ArgumentParser(description='Runs the model to output cancer_score. This is a prediction at the patient level, giving the overall patient cancer_score as outlined by Beshnova et al. \n\n**The input folder should contain subfolders with .tsv files from adaptiveBiotech for each group, and the predicted results will be saved in ./output/predicted_scores/ _input directory_ .')
    parser.add_argument('-indir', type = str, default = './SampleData/', help = 'relative path to input directory containing the Cancer/Control CDR3 sequences. Format should be .txt, with no header. By default, it is ./SampleData/')
    parser.add_argument('-outdir', type = str, default = None, help = 'Output directory name, will be located in ./output/predicted_scores/')
    parser.add_argument('-weightdir', type = str, default = 'output/training_output/', help = 'relative path to directory containing the weights of the models (.pth.tar extension).')
    #parser.add_argument('-outdir', type = str, default= 'predicted_score/', help = 'Relative path to the output directory where the best weights as well as figures, training losses/accuracies etc. are logged. By default, if it does not exist, /run_output/results/ will be created')
    parser.add_argument('-v', type=str_to_bool, default=True, help="Whether to print progress. (True/False), True by default")
    parser.add_argument('-arch', type = str, default = 'deepcat', help ='Architecture to use.')
    parser.add_argument('-enc', type = str, default = 'aaidx', help = 'Which AA encoding to use. Can be aaidx or aa_atchley. By default, it is aaidx. CHECK THAT ENCODING IS COMPATIBLE WITH THE ARCH YOU WANT TO USE!')
    parser.add_argument('-scale', type = str, default='minmax', help = 'Scaling of the features. By default, features are scaled to minmax(-1,1)')
    parser.add_argument('-thr', type = int, default = 10000, help = 'The number of rows to keep from the input .tsv file. By default, it is 10 000.')
    parser.add_argument('-save', type = str_to_bool, default = False, help = 'Whether to save the parsed .tsv file. Will not affect cancer score predictions.')
    parser.add_argument('-ismart', type = str_to_bool, default = True, help = 'Whether to run iSMART or not')


    return parser.parse_args()

def main():
    start_time = dt.now()
    args = args_parser()    
    KEYS = [12,13,14,15,16]
    arch = args.arch.lower()
    encoding = args.enc.lower()
    scaling = args.scale.lower()
    ISMART = args.ismart
    #cuda check
    if torch.cuda.is_available():
        DEVICE = torch.device('cuda')
        print("Using : {}".format(DEVICE))
    else:
        DEVICE = torch.device('cpu')
        print("Using : {}".format(DEVICE))
    #Output folder check
    OUTDIR = './output/predicted_scores/'
    if not os.path.exists(OUTDIR):
        os.makedirs(OUTDIR, exist_ok = True)    
    #Load the models & send to evalmode+device
    models = load_models(args.weightdir, KEYS, arch=arch)
    
    for k in models.keys():
        models[k].eval()
        models[k].to(DEVICE)
            #os.path.basename(os.path.dirname('/run_output/ostmeyer_colorectal_deepcat/'))
    if args.outdir is not None:
        basename = args.outdir
    else : 
        basename = os.path.basename(os.path.dirname(args.indir))
    OUTDIR = os.path.join(OUTDIR, basename)
    
    if not os.path.exists(OUTDIR):
        os.makedirs(OUTDIR, exist_ok = True)   
    #For now, want to work with SampleData and assumes that there are multiple folders within the input folder
    #ex, iterate over the following folders : ./SampleData/Cancer and ./SampleData/Control
    if args.save:
        parsed=os.path.join(OUTDIR,'parsed/')
        if not os.path.exists(parsed):
            os.makedirs(parsed, exist_ok = True)  
    else : parsed=''
    for subfolder in os.listdir(args.indir): #For each folder in in_directory
        subfolderpath = os.path.join(args.indir, subfolder)#Get path to subfolder
        #Listing the .txt files that are in this folder
        files = [os.path.join(subfolderpath,x) for x in os.listdir(subfolderpath) if x.endswith('.tsv')]
        scores = []
        if len(files) == 0:continue
        #Iterating over each file and getting the scores for each file
        for filename in files:
            df = read_adaptive_tsv(filename, save=args.save, threshold = args.thr, savedir = parsed)
            if type(pd.DataFrame())!=pd.core.frame.DataFrame:
                print("Couldn't read {}. Skipping file".format(os.path.basename(filename)))
                continue
            if len(df)>=args.thr and ISMART==True:
                df = ismart(df, save=args.save, name = filename, savedir = parsed)
            df['len']=df.amino_acid.str.len()
            cancer_score = predict_score(models, df, device=DEVICE, encoding=encoding, scaling = scaling)
            scores.append(cancer_score)
            
        #Getting the mapping and saving key:value with key = filename, value = cancer score
        MAPPING = {os.path.basename(file):cancer_score for (file,cancer_score) in zip(files,scores)}
        sub_basename = os.path.basename(subfolderpath)
        with open(os.path.join(OUTDIR,sub_basename+'_cancer_scores.txt'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter = '\t')
            writer.writerows(zip(MAPPING.keys(), MAPPING.values()))
            
    with open(os.path.join(OUTDIR,'args.txt'), 'w') as f:
        d = vars(args)
        f.write("###### ARGS::\n")
        for k in d.keys():
            f.write("{}:{}\n".format(k, d[k]))
    end_time = dt.now()       
    elapsed = divmod((end_time-start_time).total_seconds(), 60)
    print("\nTime elapsed:\n\t{} minutes\n\t{} seconds".format(elapsed[0], elapsed[1]))

if __name__ == '__main__':
    main()

    
    