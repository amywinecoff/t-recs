import numpy as np
from recommender import Recommender
from measurements import Measurements
from user_scores import ActualUserScores
import matplotlib.pyplot as plt

class ContentFiltering(Recommender):
    def __init__(self, num_users, num_items, item_representation=None, num_attributes=None,
        num_items_per_iter=10, randomize_recommended=True, num_recommended=None,
        num_new_items=None, actual_user_scores=True, debugger=None, measurements=None):
        if num_attributes is None:
            num_attributes = int(num_items - num_items / 10)
        #self.num_attributes = num_attributes
        self.binary = True
        if item_representation is None:
            measurements = Measurements(debugger)
            self.item_attributes = self._init_random_item_attributes(num_attributes, 
                num_items, binary=self.binary)
        else:
            self.item_attributes = item_representation
            measurements = Measurements(debugger)
        # TODO: user profiles should be learned from users' interactions
        self.user_profiles = np.zeros((num_users, num_items), dtype=int)
        if actual_user_scores:
            actual_scores = ActualUserScores(num_users, self.item_attributes, 
                debugger, distribution=np.random.normal, normalize=True,
                loc=0, scale=num_users/50)
        else:
            actual_scores = None
        super().__init__(num_users, num_items, num_items_per_iter,
            randomize_recommended, num_recommended, num_new_items,
            actual_scores, measurements, debugger)
        self.debugger.log('Type of recommendation system: %s' % __name__)
        self.debugger.log('Num attributes: %d' % self.item_attributes.shape[0])
        self.debugger.log('Attributes of each item (rows):\n%s' % \
            (str(self.item_attributes.T)))
        self.debugger.log('User profiles known to the system represented by their ' + \
            'attributes:\n%s' % str(self.user_profiles))

    def _init_random_item_attributes(self, num_attributes, num_items, binary=False):
        # TODO: attributes from distributions
        if binary:
            dist = np.random.binomial(1, .3, size=(num_items, num_attributes))
        else: # 
            dist = np.random.random(size=(num_items, num_attributes))
            dist = dist / dist.sum(axis=1)[:,None]
        '''
        # Is there any row with all item attributes set to zero?
        rows_not_zeros = np.any(dist > 0, axis=1)
        # If so, change a random element in the row(s) to one
        if False in rows_not_zeros:
            row = np.where(rows_not_zeros == False)[0]
            col = np.random.randint(0, num_attributes, size=(row.size))
            dist[row, col] = 1
        '''
        return dist.T#.astype(int)

    def _init_user_profiles(self, num_attributes, num_users):
        # Real numbers
        # TODO: non-random attributes?
        dist = abs(np.random.normal(0, 0.8, size=(num_users, num_attributes)))
        # Is there any row with all item attributes set to zero?
        rows_not_zeros = np.any(dist > 0, axis=1)
        # If so, change a random element in the row(s)
        if False in rows_not_zeros:
            row = np.where(rows_not_zeros == False)[0]
            col = np.random.randint(0, num_attributes, size=(row.size))
            dist[row, col] = np.random.rand()
        return dist

    def _store_interaction(self, interactions):
        interactions_per_user = np.zeros((self.num_users, self.num_items))
        interactions_per_user[self.user_vector, interactions] = 1
        user_attributes = np.dot(interactions_per_user, self.item_attributes.T)
        self.user_profiles = np.add(self.user_profiles, user_attributes)

    def _expand_items(self, num_new_items=None):
        if num_new_items is None:
            num_new_items = 2 * self.num_items_per_iter
        super()._expand_items(num_new_items)
        num_attributes = self.item_attributes.shape[0]
        new_item_attributes = self._init_random_item_attributes(num_attributes, 
            num_new_items, self.binary)
        self.item_attributes = np.concatenate((self.item_attributes, new_item_attributes),
            axis=1)
        self.actual_user_scores.expand_items(self.item_attributes)
        self.train()

    def train(self):
        # Normalize user_profiles
        user_profiles = self.user_profiles / self.user_profiles.sum(axis=1)[:,None]
        super().train(user_profiles=user_profiles)

    def interact(self, step=None, startup=False, measurement_visualization_rule=False):
        if startup:
            num_new_items = self.num_items_per_iter
            num_recommended = 0
        elif self.randomize_recommended:
            num_new_items = np.random.randint(0, self.num_items_per_iter)
            num_recommended = self.num_items_per_iter-num_new_items
        else:
            # TODO: these may be constants or iterators on vectors
            num_new_items = self.num_new_items
            num_recommended = self.num_recommended
        interactions = super().interact(num_recommended, num_new_items)
        self.measure_equilibrium(interactions, step=step, 
            measurement_visualization_rule=measurement_visualization_rule)
        self._store_interaction(interactions)
        self.debugger.log("System updates user profiles based on last interaction:\n" + \
            str(self.user_profiles.astype(int)))

    def recommend(self, k=1, indices_prime=None):
        return super().recommend(k=k, indices_prime=indices_prime)

    def startup_and_train(self, timesteps=50, 
        measurement_visualization_rule= lambda x: False):
        self.debugger.log('Startup -- recommend random items')
        return self.run(timesteps, startup=True, train_between_steps=False, 
            measurement_visualization_rule=measurement_visualization_rule)

    def run(self, timesteps=50, startup=False, train_between_steps=True,
                                     measurement_visualization_rule=lambda x: False):
        if not startup:
            self.debugger.log('Run -- interleave recommendations and random items ' + \
                'from now on')
        #self.measurements.set_delta(timesteps)
        for t in range(timesteps):
            self.debugger.log('Step %d' % t)
            self.interact(step=t, startup=startup, 
                measurement_visualization_rule=measurement_visualization_rule(t))
            #super().run(startup=False, train=train, step=step)
            if train_between_steps:
                self.train()
        # If no training in between steps, train at the end: 
        if not train_between_steps:
            self.train()
        #return super().run(timesteps, startup=False, train=train)

    def get_heterogeneity(self):
        return self.measurements.get_delta()

    def measure_equilibrium(self, interactions, step, measurement_visualization_rule=False):
        return self.measurements.measure_equilibrium(step, interactions, self.num_users,
            self.num_items, visualize=measurement_visualization_rule)