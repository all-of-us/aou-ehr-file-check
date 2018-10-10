# Erroneous Files

All the example data was taken from [pitt_five_person](https://github.com/all-of-us/curation/blob/develop/data_steward/test/test_data/pitt_five_person/)

 * "person.csv" has the columns "birth_datetime" and "day_of_birth" interchanged
 * "drug_exposure.csv" has the column "person_id" missing
 * "drug_exposure.csv" has the column "drug_id" added but it is not in the specifications under [resources/omop/dose_era.json](https://github.com/all-of-us/aou-ehr-file-check/tree/master/resources/omop/dose_era.json)
 * "condition.csv" is an erroneous filename since it is not in line with the specifications under [resources/omop](https://github.com/all-of-us/aou-ehr-file-check/tree/master/resources/omop)
 * "measurement.csv" has "person_id" as NULL in row 3 (line number 4) but it is a required value
 * "observation.csv" has an incorrect data type in the column "observation_type_concept_id" and row 2 (line number 3), with "string" instead of "integer"
