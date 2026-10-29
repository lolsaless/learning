# 정리 전
ggplot(data, aes(x, y)) +
  geom_point()

# 정리 후
ggplot(data, aes(x, y)) +
  geom_point()


test

test

library(dplyr)
library(ggplot2)

result <- mtcars %>%
  filter(cyl %in% c(4, 6, 8), mpg > 15, hp > 90) %>%
  mutate(power_weight_ratio = hp / wt, efficiency_score = mpg / hp * 100) %>%
  group_by(cyl) %>%
  summarise(
    avg_mpg = mean(mpg),
    avg_hp = mean(hp),
    avg_ratio = mean(power_weight_ratio),
    avg_eff = mean(efficiency_score),
    n = n()
  ) %>%
  arrange(desc(avg_eff))

ggplot(result, aes(x = cyl, y = avg_eff, fill = factor(cyl))) +
  geom_col(width = 0.6) +
  geom_text(aes(label = round(avg_eff, 2)), vjust = -0.5, size = 4) +
  labs(
    title = "Efficiency score by cylinder",
    subtitle = "Calculated from mtcars dataset using multiple transformations",
    x = "Number of cylinders",
    y = "Efficiency score",
    fill = "Cylinder"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 16, face = "bold"),
    legend.position = "top"
  )

library(dplyr)
library(ggplot2)

result <- mtcars %>%
  filter(cyl %in% c(4, 6, 8), mpg > 15, hp > 90) %>%
  mutate(power_weight_ratio = hp / wt, efficiency_score = mpg / hp * 100) %>%
  group_by(cyl) %>%
  summarise(
    avg_mpg = mean(mpg),
    avg_hp = mean(hp),
    avg_ratio = mean(power_weight_ratio),
    avg_eff = mean(efficiency_score),
    n = n()
  ) %>%
  arrange(desc(avg_eff))

ggplot(result, aes(x = cyl, y = avg_eff, fill = factor(cyl))) +
  geom_col(width = 0.6) +
  geom_text(aes(label = round(avg_eff, 2)), vjust = -0.5, size = 4) +
  labs(
    title = "Efficiency score by cylinder",
    subtitle = "Calculated from mtcars dataset using multiple transformations",
    x = "Number of cylinders",
    y = "Efficiency score",
    fill = "Cylinder"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 16, face = "bold"),
    legend.position = "top"
  )


ggplot()

mean_mpg
mean_hp
mean_wt

median <- mean(mtcars$mpg)
mean_hp <- mean(mtcars$hp)
mean_wt <- mean(mtcars$wt)

