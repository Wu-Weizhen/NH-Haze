import os
os.environ['CUDA_VISIBLE_DEVICES'] = '0,1'

import tqdm
import numpy as np

from core.utils import load_images_with_crop_flip_data_aug
from core.losses import wasserstein_loss, perceptual_and_l2_loss
# from core.new_losses import wasserstein_loss, perceptual_and_l2_loss
from core.networks import unet_spp_large_swish_generator_model, unet_encoder_discriminator_model, gan_model
# from core.new_networks import unet_spp_large_swish_generator_model, unet_encoder_discriminator_model, gan_model

from keras.optimizers import Adam
import keras

BASE_DIR = 'weights'

d_weight_path = "./weights/d/discriminator_40.h5"
g_weight_path = "./weights/g/generator_40_149.h5"


def save_all_weights(d, g, epoch_number, current_loss):
    save_dir_g = os.path.join(BASE_DIR, 'g')
    if not os.path.exists(save_dir_g):
        os.makedirs(save_dir_g)

    save_dir_d = os.path.join(BASE_DIR, 'd')
    if not os.path.exists(save_dir_d):
        os.makedirs(save_dir_d)

    g.save_weights(os.path.join(save_dir_g, 'generator_{}_{}.h5'.format(epoch_number, current_loss)), True)
    d.save_weights(os.path.join(save_dir_d, 'discriminator_{}.h5'.format(epoch_number)), True)


# def train_multiple_outputs(n_images, batch_size, log_dir, epoch_num, critic_updates=5):
def train(n_images, batch_size, log_dir, epoch_num, critic_updates=5):

    # data = load_images_with_crop_flip_data_aug('path/to/data', n_images)
    data = load_images_with_crop_flip_data_aug('./data', n_images)
    y_train, x_train = data['B'], data['A']

    print("Total data:", len(y_train))

    g1 = unet_spp_large_swish_generator_model()
    d1 = unet_encoder_discriminator_model()
    d_on_g1 = gan_model(g1, d1)

    # # 跑双显卡把51-53行注释取消
    # g =  keras.utils.multi_gpu_model(g, gpus=2)
    # d =  keras.utils.multi_gpu_model(d, gpus=2)
    # d_on_g =  keras.utils.multi_gpu_model(d_on_g, gpus=2)

    # # Load pre-trained weights
    # if g_weight_path != "" and d_weight_path != "":
    #     g.load_weights(g_weight_path)
    #     d.load_weights(d_weight_path)

    # Load pre-trained weights     
    if g_weight_path != "":
        g1.load_weights(g_weight_path)
    if d_weight_path != "":
        d1.load_weights(d_weight_path)


    # 跑双显卡把下面三行注释取消
    g =  keras.utils.multi_gpu_model(g1, gpus=2)
    d =  keras.utils.multi_gpu_model(d1, gpus=2)
    d_on_g =  keras.utils.multi_gpu_model(d_on_g1, gpus=2)


    lr = 1E-4
    decay_rate = lr/epoch_num

    # d_opt = Adam(lr=1E-4, beta_1=0.9, beta_2=0.999, epsilon=1e-08)
    # d_on_g_opt = Adam(lr=1E-4, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

    d_opt = Adam(lr=lr, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=decay_rate)
    d_on_g_opt = Adam(lr=lr, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=decay_rate)


    d.trainable = True
    d.compile(optimizer=d_opt, loss=wasserstein_loss)
    d.trainable = False

    # loss = [perceptual_loss, wasserstein_loss]
    loss = [perceptual_and_l2_loss, wasserstein_loss]

    loss_weights = [100, 1]

    d_on_g.compile(optimizer=d_on_g_opt, loss=loss, loss_weights=loss_weights)
    d.trainable = True

    output_true_batch, output_false_batch = np.ones((batch_size, 1)), -np.ones((batch_size, 1))

    log_path = './logs'

    for epoch in tqdm.tqdm(range(epoch_num)):

        permutated_indexes = np.random.permutation(x_train.shape[0])

        d_losses = []
        d_on_g_losses = []
        for index in range(int(x_train.shape[0] / batch_size)):
            batch_indexes = permutated_indexes[index*batch_size:(index+1)*batch_size]

            image_blur_batch = x_train[batch_indexes]
            image_full_batch = y_train[batch_indexes]


            generated_images = g.predict(x=image_blur_batch, batch_size=batch_size)

            for _ in range(critic_updates):
                d_loss_real = d.train_on_batch(image_full_batch, output_true_batch)
                d_loss_fake = d.train_on_batch(generated_images, output_false_batch)
                d_loss = 0.5 * np.add(d_loss_fake, d_loss_real)
                d_losses.append(d_loss)

            d.trainable = False

            d_on_g_loss = d_on_g.train_on_batch(image_blur_batch, [image_full_batch, output_true_batch])
            d_on_g_losses.append(d_on_g_loss)

            d.trainable = True

        print("DLoss:", np.mean(d_losses), "- GLoss", np.mean(d_on_g_losses))

        epoch_ = epoch+1
        if epoch_ % 20 == 0:
            save_all_weights(d1, g1, epoch_, int(np.mean(d_on_g_losses)))



if __name__ == '__main__':

    # Train Parameters:
    n_images = 40
    batch_size = 2
    log_dir = False
    epoch_num = 60
    critic_updates = 1

    # Train Network
    train(n_images, batch_size, log_dir, epoch_num, critic_updates)



